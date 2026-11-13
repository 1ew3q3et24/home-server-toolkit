package com.lzj.mcgate;

import org.bukkit.plugin.java.JavaPlugin;

public class McGate extends JavaPlugin {

    private Backend backend;
    private Gate gate;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        backend = new Backend(this);
        gate = new Gate(this, backend);
        getServer().getPluginManager().registerEvents(gate, this);
        // 轮询"已验证"名单 (异步), 每 3 秒一次
        getServer().getScheduler().runTaskTimerAsynchronously(this, () -> gate.poll(), 100L, 60L);
        getLogger().info("McGate 已启用 v" + getDescription().getVersion());
    }

    @Override
    public void onDisable() {
        if (gate != null) gate.shutdown();
        getLogger().info("McGate 已停用");
    }
}