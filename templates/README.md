# 模板库

本目录保存公开分发的模板 ZIP 和 `index.json` 清单。模板与 Skill 同级，安装 Skill 时不预先下载模板；使用时按模板 ID 单独下载。

## 添加一个模板

1. 使用现有画布模板打包流程生成自包含 ZIP，包内保留 `canvas-template.json`、工程、封面、预览及必要许可。与客户端服务端使用同一份 ZIP，不另做一套模板格式。
2. 将 ZIP 放到本目录，或者发布为 GitHub Release 附件。
3. 在 `index.json` 的 `templates` 数组加入一条记录。`id` 与包内 `manifest.id` 一致，且在清单中唯一；客户端服务端的下载 slug 可以不同。
4. 计算实际 ZIP 的 SHA256，填入 `sha256`。修改 ZIP 后同步更新哈希；下载工具不会使用哈希不匹配的文件。

记录格式示例（仅说明格式，不是已发布模板）：

```json
{
  "id": "example-16x9",
  "name": "示例模板",
  "orientation": "landscape",
  "theme": "light",
  "description": "模板风格说明",
  "download_url": "./example-16x9.zip",
  "sha256": "替换为实际 ZIP 的 64 位十六进制 SHA256",
  "min_skill_version": "0.10.0"
}
```

`download_url` 可以是相对 `index.json` 的 ZIP 路径，也可以是实际可访问的 HTTPS Release 下载地址。`id`、`name`、`download_url`、`sha256` 为必需项，其余是选用元数据；实际兼容性以包内清单为准。新模板 ZIP 加入后，清单仍保持 `schema_version: 1`。

Windows 下可使用以下命令计算哈希：

```powershell
Get-FileHash -LiteralPath .\templates\example-16x9.zip -Algorithm SHA256
```

本地验证一个已经登记的模板：

```text
python xycut-huabu-skill/scripts/download_template.py --template-id example-16x9 --index templates/index.json --cache-dir .cache/templates
```

远程使用时通常省略 `--index`，按 Skill 默认的 GitHub 清单获取。无论清单中有多少套模板，每次只下载选中的一个 ZIP；缓存中已有且哈希正确时复用，不重复下载。

## 代码许可与素材说明

每个模板 ZIP 的根目录和 `project/` 工程内均提供 `LICENSE`、`THIRD_PARTY_NOTICES.md`，以及实际字体需要的 `LICENSES/`。自有代码按 MIT 授权，版权人为大圆（dayuanlog）。工程内也保留这些文件，确保 Agent 复制任务后仍可查阅许可。

字体、图标保留原版权和许可。示例数字人、AI 配音和音效用于展示模板效果，不随代码 MIT 额外授予素材使用权。说明保持简洁，具体资源名称和对应原协议放在各包的 `LICENSES/`。

新增模板应保留相同的许可结构和实际来源记录。修改 ZIP 内任意说明或文件后，都需重新计算 `sha256`，并同步 `size_bytes`。
