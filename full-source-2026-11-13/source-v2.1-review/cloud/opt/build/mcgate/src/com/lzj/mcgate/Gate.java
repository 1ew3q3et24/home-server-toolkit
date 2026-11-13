package com.lzj.mcgate;

import io.papermc.paper.event.player.AsyncChatEvent;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.event.ClickEvent;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** 闸门主体: 冻结 / 私发验证码 / 轮询解锁 / 超时踢出 */
public class Gate implements Listener {

    private final JavaPlugin plugin;
    private final Backend backend;
    private final Map<UUID, Frozen> frozen = new ConcurrentHashMap<>();

    public Gate(JavaPlugin plugin, Backend backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    private static class Frozen {
        String name;
        Location loc;
        String code;
        String link;
        boolean needTos;
        BukkitTask kickTask;
        BukkitTask remindTask;
    }

    private void sendLink(Player p, String link) {
        if (link == null || link.isEmpty()) return;
        p.sendMessage(Component.text("点击打开认证：")
                .color(NamedTextColor.RED)
                .append(Component.text(link)
                        .color(NamedTextColor.AQUA)
                        .clickEvent(ClickEvent.openUrl(link))));
    }

    private String color(String s) { return s == null ? "" : s.replace('&', '\u00a7'); }

    private String msg(String code) {
        String t = plugin.getConfig().getString("gate.message", "&c请到 chat.lzj2012.top 发送验证码: &e{code}");
        return color(t.replace("{code}", code == null ? "" : code));
    }

    private String tosMsg() {
        return color(plugin.getConfig().getString("gate.tos-message",
                "&c请打开 &fmcverify.lzj2012.top &c阅读并同意《用户协议》，同意后会自动解锁。"));
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        final Player player = event.getPlayer();
        final String name = player.getName();
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            Backend.CheckResult cr = backend.check(name);
            if (cr.needTos) {
                Bukkit.getScheduler().runTask(plugin, () -> freeze(player, null, null, true));
                return;
            }
            if (!cr.needVerify || cr.code == null) return;
            Bukkit.getScheduler().runTask(plugin, () -> freeze(player, cr.code, cr.link, false));
        });
    }

    private void freeze(Player player, String code, String link, boolean needTos) {
        if (frozen.containsKey(player.getUniqueId())) return;
        final Frozen f = new Frozen();
        f.name = player.getName();
        f.loc = player.getLocation().clone();
        f.code = code;
        f.link = link;
        f.needTos = needTos;
        frozen.put(player.getUniqueId(), f);
        player.setInvulnerable(true);
        if (needTos) {
            player.sendTitle(color(plugin.getConfig().getString("gate.tos-title", "&c请先同意用户协议")),
                    color(plugin.getConfig().getString("gate.tos-subtitle", "&f打开 mcverify.lzj2012.top")), 10, 100, 20);
            player.sendMessage(tosMsg());
        } else {
            player.sendTitle(color(plugin.getConfig().getString("gate.title", "&c访问受限")),
                    color(plugin.getConfig().getString("gate.subtitle", "&f请到聊天室验证")), 10, 100, 20);
            player.sendMessage(msg(code));
            sendLink(player, link);
        }
        int timeout = plugin.getConfig().getInt("gate.timeout-seconds", 300);
        f.kickTask = Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (frozen.containsKey(player.getUniqueId())) {
                frozen.remove(player.getUniqueId());
                if (f.remindTask != null) f.remindTask.cancel();
                String kickKey = needTos ? "gate.tos-kick-reason" : "gate.kick-reason";
                String kickDef = needTos ? "&c未同意用户协议。请打开 mcverify.lzj2012.top 同意后再进服。" : "&c验证超时";
                player.kickPlayer(color(plugin.getConfig().getString(kickKey, kickDef)));
            }
        }, timeout * 20L);
        f.remindTask = Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            if (player.isOnline()) player.sendMessage(f.needTos ? tosMsg() : msg(f.code));
        }, 300L, 300L);
    }

    public void shutdown() {
        for (UUID id : new ArrayList<>(frozen.keySet())) {
            Player p = Bukkit.getPlayer(id);
            if (p != null) p.setInvulnerable(false);
        }
        for (Frozen f : new ArrayList<>(frozen.values())) {
            if (f.kickTask != null) f.kickTask.cancel();
            if (f.remindTask != null) f.remindTask.cancel();
        }
        frozen.clear();
    }

    private void unlock(Player player, boolean tosOnly) {
        Frozen f = frozen.remove(player.getUniqueId());
        if (f == null) return;
        if (f.kickTask != null) f.kickTask.cancel();
        if (f.remindTask != null) f.remindTask.cancel();
        player.setInvulnerable(false);
        if (!tosOnly && plugin.getConfig().getBoolean("gate.whitelist-add", true)) {
            Bukkit.dispatchCommand(Bukkit.getConsoleSender(), "whitelist add " + f.name);
        }
        if (tosOnly) {
            player.sendTitle(color("&a协议已确认"), color("&f祝你玩得开心"), 10, 60, 20);
            player.sendMessage(color("&a✔ 用户协议已确认，已解锁全部权限"));
        } else {
            player.sendTitle(color("&a验证通过"), color("&f祝你玩得开心"), 10, 60, 20);
            player.sendMessage(color("&a✔ 验证通过，已解锁全部权限"));
        }
    }

    /** 由异步定时器调用 */
    public void poll() {
        if (frozen.isEmpty()) return;
        List<String> done = backend.pending();
        List<String> tosNames = new ArrayList<>();
        for (Map.Entry<UUID, Frozen> en : frozen.entrySet()) {
            if (en.getValue().needTos) tosNames.add(en.getValue().name);
        }
        List<String> agreed = tosNames.isEmpty() ? new ArrayList<>() : backend.tosCheck(tosNames);
        if (done.isEmpty() && agreed.isEmpty()) return;
        Bukkit.getScheduler().runTask(plugin, () -> {
            List<Player> targets = new ArrayList<>();
            for (String n : done) {
                Player p = Bukkit.getPlayerExact(n);
                Frozen f = p == null ? null : frozen.get(p.getUniqueId());
                if (p != null && f != null && !f.needTos) targets.add(p);
            }
            for (Player p : targets) unlock(p, false);
            for (String n : agreed) {
                Player p = Bukkit.getPlayerExact(n);
                if (p == null) continue;
                Frozen f = frozen.get(p.getUniqueId());
                if (f != null && f.needTos) unlock(p, true);
            }
        });
        if (!done.isEmpty()) backend.ack(done);
    }

    private boolean isFrozen(Player p) { return p != null && frozen.containsKey(p.getUniqueId()); }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onMove(PlayerMoveEvent e) {
        Frozen f = frozen.get(e.getPlayer().getUniqueId());
        if (f == null) return;
        Location from = e.getFrom();
        Location to = e.getTo();
        if (to == null) return;
        if (from.getX() != to.getX() || from.getY() != to.getY() || from.getZ() != to.getZ()) {
            e.setTo(f.loc.clone());
        }
    }

    @EventHandler public void onBreak(BlockBreakEvent e) { if (isFrozen(e.getPlayer())) e.setCancelled(true); }
    @EventHandler public void onPlace(BlockPlaceEvent e) { if (isFrozen(e.getPlayer())) e.setCancelled(true); }
    @EventHandler public void onInteract(PlayerInteractEvent e) { if (isFrozen(e.getPlayer())) e.setCancelled(true); }
    @EventHandler public void onDrop(PlayerDropItemEvent e) { if (isFrozen(e.getPlayer())) e.setCancelled(true); }

    @EventHandler
    public void onDamage(EntityDamageEvent e) {
        if (e.getEntity() instanceof Player) {
            if (isFrozen((Player) e.getEntity())) e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onChat(AsyncChatEvent e) {
        final Frozen f = frozen.get(e.getPlayer().getUniqueId());
        if (f == null) return;
        e.setCancelled(true);
        final Player p = e.getPlayer();
        final String m = f.needTos ? tosMsg() : msg(f.code);
        final String lk = f.link;
        Bukkit.getScheduler().runTask(plugin, () -> { p.sendMessage(m); sendLink(p, lk); });
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        Frozen f = frozen.remove(e.getPlayer().getUniqueId());
        if (f != null) {
            if (f.kickTask != null) f.kickTask.cancel();
            if (f.remindTask != null) f.remindTask.cancel();
        }
    }
}
