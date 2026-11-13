
import pathlib
base = pathlib.Path('/opt/build/mcgate/src/com/lzj/mcgate')
g = base/'Gate.java'
s = g.read_text()
s = s.replace('import org.bukkit.scheduler.BukkitTask;', 'import org.bukkit.scheduler.BukkitTask;\nimport net.kyori.adventure.text.Component;\nimport net.kyori.adventure.text.format.NamedTextColor;\nimport net.kyori.adventure.text.event.ClickEvent;')
s = s.replace('        String code;\n        boolean needTos;', '        String code;\n        String link;\n        boolean needTos;')
s = s.replace('freeze(player, null, true)', 'freeze(player, null, null, true)')
s = s.replace('freeze(player, cr.code, false)', 'freeze(player, cr.code, cr.link, false)')
s = s.replace('private void freeze(Player player, String code, boolean needTos) {', 'private void freeze(Player player, String code, String link, boolean needTos) {')
s = s.replace('        f.code = code;\n        f.needTos = needTos;', '        f.code = code;\n        f.link = link;\n        f.needTos = needTos;')
s = s.replace('            player.sendMessage(msg(code));', '            player.sendMessage(msg(code));\n            sendLink(player, link);')
s = s.replace('        final String m = f.needTos ? tosMsg() : msg(f.code);\n        Bukkit.getScheduler().runTask(plugin, () -> p.sendMessage(m));',
              '        final String m = f.needTos ? tosMsg() : msg(f.code);\n        final String lk = f.link;\n        Bukkit.getScheduler().runTask(plugin, () -> { p.sendMessage(m); sendLink(p, lk); });')
s = s.replace('    private String color(String s) {', '''    private void sendLink(Player p, String link) {
        if (link == null || link.isEmpty()) return;
        p.sendMessage(Component.text("点击打开认证：")
                .color(NamedTextColor.RED)
                .append(Component.text(link)
                        .color(NamedTextColor.AQUA)
                        .clickEvent(ClickEvent.openUrl(link))));
    }

    private String color(String s) {''')
g.write_text(s)

b = base/'Backend.java'
s = b.read_text()
s = s.replace('        public String code;\n        public int expiresIn = 300;', '        public String code;\n        public String link;\n        public int expiresIn = 300;')
s = s.replace('if (r.has("code") && !r.get("code").isJsonNull()) cr.code = r.get("code").getAsString();', 'if (r.has("code") && !r.get("code").isJsonNull()) cr.code = r.get("code").getAsString();\n            if (r.has("link") && !r.get("link").isJsonNull()) cr.link = r.get("link").getAsString();')
b.write_text(s)
print('PATCHED')
