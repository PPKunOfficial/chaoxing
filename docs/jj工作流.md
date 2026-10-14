# Jujutsu 工作流

本项目使用 [Jujutsu](https://docs.jj-vcs.dev/latest/) 的 Git 后端，兼容 GitHub。colocated 模式由 `.jj/` 管理工作区，`.git/` 保留 Git 后端、历史和远端兼容性；不要删除 `.git/`。

## 克隆与迁移

```bash
jj git clone https://github.com/Samueli924/chaoxing chaoxing
cd chaoxing
```

其他现有 Git 克隆可迁移，不需要重新提交历史：

```bash
jj git init --colocate
jj bookmark track main@origin
```

## 日常提交

Jujutsu 自动记录工作区，不需要 `git add` 或 `git commit`。一次 change 一件事，提交信息采用 gitmoji + 约定式提交 + 中文：

```bash
jj status
jj diff
jj commit -m "♻️ refactor(app): 拆分命令行应用职责"
```

`jj commit` 完成当前 change 并创建新的空工作 change，也可分别运行 `jj describe -m "..."` 和 `jj new`。通过 `jj log` 查看 change ID；引用改动用 change ID，不用会被改写的 commit hash。

仓库存在 `.jj/` 时不要混用会修改状态的 Git 命令。不要把临时文件、账号、Cookie 或 API key 纳入 change；`.gitignore` 同样适用于 Jujutsu，`.jj/` 不入库。

## 获取与发布

```bash
jj git fetch
jj bookmark set <书签名> -r <change-id>
jj git push --bookmark <书签名>
```

书签不会因新提交自动推进；提交与发布是两步独立操作。修改已推送的书签前先确认；首次发布新书签按 Jujutsu 提示建立远端跟踪。远端变化导致推送拒绝时先 fetch 并解决差异，不绕过检查。
