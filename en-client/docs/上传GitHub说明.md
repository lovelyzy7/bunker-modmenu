# 上传到 GitHub 说明

本仓库已按"源码入库、大文件排除"的方式整理：
源码 / 文档 / 工具 / 模板入库，大文件（APK / dump / 工作区）通过 Release 分发。

---

## 1. 推送到 GitHub（新仓库）

在 GitHub 上先创建**空仓库**（不要勾选初始化 README / .gitignore / LICENSE），然后本地：

```bash
cd <仓库根>
# 若还没有 origin：
git remote add origin https://github.com/<用户名>/<仓库名>.git
# 若已有 origin（换地址）：
git remote set-url origin https://github.com/<用户名>/<仓库名>.git

git branch -M main
git push -u origin main
```

推送方式二选一：
- **保留完整历史**（推荐，能看到开发过程）：直接 `git push -u origin main`
- **只留一个初始提交**（更清爽）：
  ```bash
  git checkout --orphan main-clean
  git add -A
  git commit -m "初始化：NieR Reincarnation 内置 Mod 菜单（源码/文档/工具/模板）"
  git branch -M main
  git push -u origin main --force
  ```

## 2. 体积说明

不含大文件时仓库约 **65 MB**（其中两个模板 zip 约 36 MB，`modmenu/` 源码约 11 MB）。
GitHub 限制：单个文件 **100 MB**（网页上传 25 MB）；普通 push 没问题，
将来若逼近上限可用 Git LFS 或 Release。

## 3. 大文件（APK / dump）怎么放

**推荐：GitHub Release 附件**（不进 Git 历史；单文件最大 2 GB）

1. 仓库 → **Releases** → *Draft a new release*（如 `v1.0.1`）
2. 上传成品 APK 作为附件
3. 说明中写清：适用客户端版本、安装注意、默认数值

**Git LFS（可选）**：GitHub 免费账号有配额（存储 / 流量各约 1 GB），
大 APK 容易超限，**更推荐用 Release 附件**。

## 4. 常见问题

| 问题 | 处理 |
|------|------|
| push 失败提示文件过大 | 确认 `.gitignore` 生效（`git status` 里不应出现 `*.apk`）；超 100 MB 改用 Release |
| 想连 `dump/` 一起传 | `dump.cs` 约 49 MB，可单独 Release 或 LFS |
| 误提交了大文件 | `git rm --cached 文件` 后重新提交；历史中的体积需 `git filter-repo` 清理 |
| 中文文件名显示乱码 | `git config core.quotepath false` |
| 强推被拒（改写历史后） | 仓库 Settings → Branches 临时允许强推，或先关闭分支保护 |
