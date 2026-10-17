# keys — JP 客户端签名密钥

| 项 | 值 |
|---|---|
| 文件 | `nier-jp.keystore`（JKS，RSA 2048，有效期 10000 天） |
| alias | `nier` |
| 密码 | `lunar-jp` |
| 证书 SHA-256 | `eec23be0cb205c401791be3d4b82e8851560f5c2aed3ec644166093d3d98a2fe` |
| 证书 DN | `CN=lunar-scripts-jp, OU=private-server, O=local, L=NA, ST=NA, C=JP` |

来源：`lunar-scripts-jp/keys/nier-jp.keystore`（JP 私服补丁脚本自带、随仓库分发的那把）。
本目录内放一份副本，保证本仓库独立可用、换机器也不变。

用途：`tools/build_all.py` 构建 JP 菜单版时用它签名。
`tools/toolpaths.json` 已指向本文件（`keys/nier-jp.keystore`）。

- 与手机上已安装的 JP 客户端**同一把 key** → `adb install -r` 可直接覆盖安装
- 用 lunar-scripts 给 JP 打私服补丁时，**也用这把 key**（全链路统一，避免来回卸载）
- **不要删除/替换**：换 key 后无法覆盖安装，只能卸载重装（进度用「データ引き継ぎ」恢复）

手工签名示例：

```bash
zipalign -p -f 4 in.apk aligned.apk
apksigner sign --ks keys/nier-jp.keystore --ks-pass pass:lunar-jp \
  --ks-key-alias nier --out out.apk aligned.apk
apksigner verify --print-certs out.apk     # 证书应等于上表 SHA-256
```
