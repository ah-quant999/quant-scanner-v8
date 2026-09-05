# v8 安全铁律（2026-09-05 起全员遵守：主人 / 小九 / 阿狸咪 / 任何 AI 助手）

## 铁律一：token 绝不写进同步盘文件

- **GitHub PAT / 任何凭证，禁止写死在任何脚本、文档、记忆文件里**（临时脚本也不行）。
- token 单点存放：`C:\Users\HH20210606\.workbuddy\v8_gh_pat`（**仓库目录外、坚果云同步范围外**）。
- 脚本需要 token 时，运行时读取该单点文件或环境变量（`V8_GH_TOKEN`）：
  ```python
  import os
  TOK = open(os.path.join(os.path.expanduser("~"), ".workbuddy", "v8_gh_pat")).read().strip()
  ```
- 仓库内旧 `.gh_pat`（.gitignore:16 保护）仅为未迁移机器的**兜底**，禁止再往仓库目录写任何含 token 的新文件。

**为什么**：`E:\workspace\stock-scanner\` 整个目录被坚果云实时同步。任何写进仓库目录的文件（包括 `.gitignore` 盖住的、`.workbuddy/` 记忆）都会同步到坚果云云端 = 第二个云副本。写死 token = 迟早泄漏。

## 铁律二：记忆/交接文件里引用凭证必须打码

写 `ghp_abcd****wxyz` 形态，禁止全文。

## 铁律三：公开仓库意识

- 本仓库是 **PUBLIC**：全部代码、算法逻辑、`raw_data/` 数据人人可见可 clone（Traffic 实测日均 ~1000 clone，多为 CI + 爬虫）。
- **禁止入仓**：个人敏感文件（身份证/家庭/私人文档）、明文凭证、内网地址密码。
- 策略参数调整默认按"会被别人看到"设计，不强求保密。

## 铁律四：写入通道最小化

- main 分支保护已开（`protected: true`），禁止在任何机器关闭或绕过。
- self-hosted runner 仅限注册过的两台：`lemoncat-cn`（小九）/ `alimi-cn`（阿狸咪）；发现陌生 runner / collaborator / deploy key / webhook 立即告警。
- PAT 遵循最小权限：新发 token 用 fine-grained（仅本仓库 + Contents:Read/Write），不再发 `repo+workflow` 全权 classic token。

## 泄漏应急（发现 token 进了公开仓库 / 同步盘云端）

1. **第一时间撤销 token**（GitHub → Settings → Developer settings → Personal access tokens），再谈其他。
2. 清理本地副本 + 坚果云网页端回收站/历史版本（本地删除不等于云端历史清空）。
3. 记录事故到 `.workbuddy/memory/`（打码形态）。
