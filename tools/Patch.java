import com.jpexs.decompiler.flash.SWF;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.avm2.AVM2Code;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.decompiler.flash.abc.avm2.parser.pcode.ASM3Parser;
import com.jpexs.decompiler.flash.abc.avm2.parser.pcode.MissingSymbolHandler;
import com.jpexs.decompiler.flash.abc.types.MethodBody;
import com.jpexs.decompiler.flash.abc.types.ScriptInfo;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.tags.ABCContainerTag;
import com.jpexs.decompiler.flash.tags.Tag;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

// usage: Patch in.swf out.swf spec.txt [spec2.txt ...]
// spec blocks:
//   === addvar NAME
//   === func NAME WHERE      WHERE = entry | exit | after:OP[/SUBSTR][:N] | before:OP[/SUBSTR][:N]   (N = 1-based occurrence, default 1)
//   === body NAME            replace the whole code (keeps traits/exceptions only if none)
//   lines: "#regs K" reserves K fresh registers referenced as {R0}..{RK-1}; "#stack N" adds N to max_stack
public class Patch {
    static MissingSymbolHandler H = new MissingSymbolHandler() {
        public boolean missingString(String v) { return true; }
        public boolean missingInt(long v) { return true; }
        public boolean missingUInt(long v) { return true; }
        public boolean missingDouble(double v) { return true; }
        public boolean missingFloat(float v) { return true; }
        public boolean missingFloat4(com.jpexs.decompiler.flash.abc.types.Float4 v) { return true; }
        public boolean missingDecimal(com.jpexs.decompiler.flash.abc.types.Decimal v) { return true; }
    };
    static class Block { String kind, name, where; String code = ""; int regs = 0, stack = 8; }
    static Map<String, Integer> ids = new LinkedHashMap<>();
    static Map<Block, java.util.regex.Pattern> pats = new HashMap<>();
    static boolean matches(Block b, String name) {
        if (b.kind.equals("funcre")) return pats.computeIfAbsent(b, k -> java.util.regex.Pattern.compile(k.name)).matcher(name).matches();
        return b.name.equals(name);
    }
    static List<AVM2Instruction> parse(ABC abc, MethodBody body, Trait t, String src) throws Exception {
        return ASM3Parser.parse(abc, new StringReader(src), t, H, body, abc.method_info.get(body.method_info)).code;
    }
    static String insText(ABC abc, AVM2Instruction ins) {
        try { return ins.toStringNoAddress(abc.constants, new ArrayList<>()); } catch (Exception e) { return ins.definition.instructionName; }
    }
    public static void main(String[] a) throws Exception {
        List<Block> blocks = new ArrayList<>();
        for (int f = 2; f < a.length; f++) {
            Block cur = null; StringBuilder sb = null;
            for (String line : Files.readAllLines(Paths.get(a[f]))) {
                if (line.startsWith("=== ")) {
                    if (cur != null) { cur.code = sb.toString(); blocks.add(cur); }
                    String[] p = line.substring(4).trim().split("\\s+");
                    cur = new Block(); cur.kind = p[0]; cur.name = p[1]; cur.where = p.length > 2 ? p[2] : "entry"; sb = new StringBuilder();
                } else if (line.startsWith("#regs ")) cur.regs = Integer.parseInt(line.substring(6).trim());
                else if (line.startsWith("#stack ")) cur.stack = Integer.parseInt(line.substring(7).trim());
                else if (cur != null) sb.append(line).append('\n');
            }
            if (cur != null) { cur.code = sb.toString(); blocks.add(cur); }
        }
        SWF swf = new SWF(new BufferedInputStream(new FileInputStream(a[0])), false);
        Set<Block> done = new HashSet<>();
        for (ABCContainerTag tag : swf.getAbcList()) {
            ABC abc = tag.getABC();
            boolean mod = false;
            // addvar: attach new slots to the script that defines C_Run.eax
            for (ScriptInfo si : abc.script_info) {
                Trait eaxT = null;
                for (Trait t : si.traits.traits) if (t.getName(abc).getName(abc.constants, null, true, false).equals("eax")) eaxT = t;
                if (eaxT == null) continue;
                for (Block b : blocks) {
                    if (!b.kind.equals("addvar")) continue;
                    // create multiname via parser on a dummy body
                    MethodBody anyBody = abc.bodies.get(0);
                    List<AVM2Instruction> ins = parse(abc, anyBody, eaxT, "getlex QName(PackageNamespace(\"C_Run\"),\"" + b.name + "\")\n");
                    int mn = ins.get(0).operands[0];
                    TraitSlotConst ts = new TraitSlotConst();
                    ts.name_index = mn; ts.kindType = Trait.TRAIT_SLOT; ts.slot_id = 0; ts.type_index = 0; ts.value_index = 0; ts.value_kind = 0;
                    si.traits.addTrait(ts);
                    si.setModified(true);
                    done.add(b); mod = true;
                    System.err.println("addvar " + b.name + " mn=" + mn);
                }
            }
            List<Object[]> methods = new ArrayList<>();
            for (ScriptInfo si : abc.script_info) for (Trait t : si.traits.traits) methods.add(new Object[]{t.getName(abc).getName(abc.constants, null, true, false), t});
            for (int ci = 0; ci < abc.instance_info.size(); ci++) {
                String cn = abc.instance_info.get(ci).getName(abc.constants).getName(abc.constants, null, true, false);
                for (Trait t : abc.instance_info.get(ci).instance_traits.traits) methods.add(new Object[]{cn + "/" + t.getName(abc).getName(abc.constants, null, true, false), t});
                for (Trait t : abc.class_info.get(ci).static_traits.traits) methods.add(new Object[]{cn + "$/" + t.getName(abc).getName(abc.constants, null, true, false), t});
            }
            for (Object[] mt : methods) {
                Trait t = (Trait) mt[1];
                if (!(t instanceof TraitMethodGetterSetter)) continue;
                String name = (String) mt[0];
                boolean any = false;
                for (Block b : blocks) if (!b.kind.equals("addvar") && matches(b, name)) any = true;
                if (!any) continue;
                int mi = ((TraitMethodGetterSetter) t).method_info;
                MethodBody body = abc.findBody(mi);
                com.jpexs.decompiler.flash.helpers.HighlightedTextWriter w = new com.jpexs.decompiler.flash.helpers.HighlightedTextWriter(new com.jpexs.decompiler.flash.helpers.CodeFormatting(), false);
                body.getCode().toASMSource(abc, abc.constants, abc.method_info.get(mi), body, com.jpexs.decompiler.flash.exporters.modes.ScriptExportMode.PCODE, w);
                List<String> lines = new ArrayList<>(Arrays.asList(w.toString().split("\n")));
                int regs = body.max_regs, stack = body.max_stack;
                final int origRegs = body.max_regs;
                for (Block b : blocks) {
                    if (b.kind.equals("addvar") || !matches(b, name)) continue;
                    String src = b.code;
                    if (b.kind.equals("funcre")) {
                        Integer id = ids.get(name);
                        if (id == null) { id = ids.size(); ids.put(name, id); }
                        src = src.replace("{ID}", String.valueOf(id));
                    }
                    for (int r = 0; r < b.regs; r++) src = src.replace("{R" + r + "}", String.valueOf(regs + r));
                    src = src.replace("{S}", String.valueOf(origRegs));
                    regs += b.regs; stack += b.stack;
                    List<String> snip = Arrays.asList(src.split("\n"));
                    int c0 = -1, c1 = -1;
                    for (int k = 0; k < lines.size(); k++) { String l = lines.get(k).trim(); if (c0 < 0 && l.equals("code")) c0 = k; if (l.startsWith("end ; code")) c1 = k; }
                    if (b.kind.equals("body")) {
                        List<String> nl = new ArrayList<>(lines.subList(0, c0 + 1)); nl.addAll(snip); nl.addAll(lines.subList(c1, lines.size()));
                        // drop exception lines when replacing whole body
                        nl.removeIf(x -> x.trim().startsWith("try from"));
                        lines = nl;
                        done.add(b); mod = true; System.err.println("body " + name); continue;
                    }
                    List<Integer> positions = new ArrayList<>();
                    if (b.where.equals("entry")) {
                        int k = c0 + 1, seen = 0;
                        while (k < c1) {
                            String l = lines.get(k).trim();
                            if (l.isEmpty() || l.endsWith(":")) { k++; continue; }
                            String op = l.split("\\s+")[0];
                            if (seen < 4 && (op.equals("getlocal0") || op.equals("pushscope") || op.equals("dup"))) { k++; seen++; continue; }
                            break;
                        }
                        // insert before any label that sits right before k
                        while (k - 1 > c0 && lines.get(k - 1).trim().endsWith(":")) k--;
                        positions.add(k);
                    } else if (b.where.equals("exit")) {
                        for (int k = c0 + 1; k < c1; k++) { String op = lines.get(k).trim().split("\\s+")[0]; if (op.equals("returnvoid") || op.equals("returnvalue")) positions.add(k); }
                    } else {
                        String[] ww = b.where.split(":");
                        String opspec = ww[1]; int nth = ww.length > 2 ? Integer.parseInt(ww[2]) : 1;
                        String op = opspec, sub = null;
                        int sl = opspec.indexOf('/'); if (sl >= 0) { op = opspec.substring(0, sl); sub = opspec.substring(sl + 1); }
                        int cnt = 0;
                        for (int k = c0 + 1; k < c1; k++) {
                            String l = lines.get(k).trim();
                            if (!l.split("\\s+")[0].equals(op)) continue;
                            if (sub != null && !l.contains(sub)) continue;
                            if (++cnt == nth) { positions.add(ww[0].equals("after") ? k + 1 : k); break; }
                        }
                        if (positions.isEmpty()) throw new RuntimeException("anchor not found: " + b.where + " in " + name);
                    }
                    Collections.sort(positions, Collections.reverseOrder());
                    int uniq = 0;
                    for (int pos : positions) {
                        List<String> sn = new ArrayList<>();
                        for (String x : snip) sn.add(x.replaceAll("\\bmd_(\\w+)", "md_$1_" + (uniq)));
                        uniq++;
                        lines.addAll(pos, sn);
                    }
                    done.add(b); mod = true;
                    if (!b.kind.equals("funcre")) System.err.println("patched " + name + " @" + b.where + " x" + positions.size());
                }
                // fix header counts
                for (int k = 0; k < lines.size(); k++) {
                    String l = lines.get(k).trim();
                    if (l.startsWith("localcount ")) lines.set(k, "localcount " + regs);
                    else if (l.startsWith("maxstack ")) lines.set(k, "maxstack " + stack);
                    else if (l.equals("code")) break;
                }
                String text = String.join("\n", lines) + "\n";
                if (System.getenv("PATCH_DUMP") != null) Files.write(Paths.get(System.getenv("PATCH_DUMP") + "/" + name.replaceAll("[^A-Za-z0-9_.$-]", "_") + ".pcode"), text.getBytes("UTF-8"));
                AVM2Code nc;
                try { nc = ASM3Parser.parse(abc, new StringReader(text), t, H, body, abc.method_info.get(mi)); }
                catch (Exception ex) { throw new RuntimeException("parse failed in " + name, ex); }
                body.setCode(nc);
                body.max_regs = regs; body.max_stack = stack;
                body.setModified();
            }
            if (mod) ((Tag) tag).setModified(true);
        }
        for (Block b : blocks) if (!done.contains(b)) throw new RuntimeException("block not applied: " + b.kind + " " + b.name);
        if (System.getenv("PATCH_MAP") != null) {
            PrintWriter pw = new PrintWriter(new FileWriter(System.getenv("PATCH_MAP")));
            for (Map.Entry<String, Integer> e : ids.entrySet()) pw.println(e.getValue() + "\t" + e.getKey());
            pw.close();
        }
        OutputStream os = new BufferedOutputStream(new FileOutputStream(a[1]));
        swf.saveTo(os);
        os.close();
    }
}
