# Canvas — R1 项目路线图

本目录是 **Canvas 源文件的唯一真源**（git 跟踪）。Cursor IDE 通过本地硬链接读取同一文件。

## 文件

| 文件 | 说明 |
|------|------|
| `r1-vlm-agent-roadmap.canvas.tsx` | R1 + RM1828 路线图（P0–P6、语音、风扇、验收命令） |

## 与 Cursor 的关系

Cursor 要求 Canvas 位于：

```
%USERPROFILE%\.cursor\projects\<workspace>\canvases\*.canvas.tsx
```

本机已建立 **硬链接**（同一文件、两个路径）：

```
canvases/r1-vlm-agent-roadmap.canvas.tsx          ← git 仓库（编辑 / 提交这里）
    ═══ 硬链接 ═══
.cursor/projects/.../canvases/r1-vlm-agent-roadmap.canvas.tsx   ← Cursor 检测用
```

在 Cursor 侧边打开 Canvas 与直接编辑仓库内文件 **完全等价**。

### 软链接 vs 硬链接（Windows）

| 方式 | 本机 | 说明 |
|------|------|------|
| **硬链接** | ✅ 已用 | 同盘、无需管理员；git clone 后需在本机重建链接 |
| **软链接 symlink** | ⚠️ 需开发者模式或管理员 | 跨盘可用；`git clone` 在其他机器默认可还原为相对路径链接 |

`.cursor/` 目录 **不在 git 内**；clone 仓库后运行一次：

```powershell
# 在仓库根目录执行（PowerShell）
$repo = (Resolve-Path ".\canvases\r1-vlm-agent-roadmap.canvas.tsx").Path
$ws   = "$env:USERPROFILE\.cursor\projects\c-Users-wwff-Documents-youyeetoo3588s\canvases"
New-Item -ItemType Directory -Force -Path $ws | Out-Null
$dst  = Join-Path $ws "r1-vlm-agent-roadmap.canvas.tsx"
if (-not (Test-Path $dst)) {
  cmd /c mklink /H "$dst" "$repo"
}
```

### 不要提交的运行时文件

以下由 Cursor 自动生成，留在 `.cursor/projects/.../canvases/`，**勿放入 git**：

- `*.canvas.data.json`
- `*.canvas.status.json`
- `node_modules/`

## 打开方式

1. Cursor 聊天里点击 Canvas 卡片
2. 命令面板：**View → Open Canvas**
3. 直接编辑本目录下的 `.canvas.tsx`

## 在线分享

Canvas 工具栏 **Publish** → 团队浏览器链接。见 Cursor 文档 [Sharing canvases](https://cursor.com/docs/agent/tools/canvas#sharing-canvases)。
