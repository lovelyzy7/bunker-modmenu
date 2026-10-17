# keys — EN 客户端签名密钥

| 项 | 值 |
|---|---|
| 文件 | `debug.keystore`（JKS；Android 标准 debug 钥匙库） |
| alias | `androiddebugkey` |
| 密码 | `android` |
| 证书 SHA-256 | `7d792c3cfefd73223764206edebd9526618638ff152165df5fbecd356aa4a173` |
| 证书 DN | `C=US, O=Android, CN=Android Debug` |

用途：`tools/build_all.py` 一键构建结束时用它给最终 APK 重新签名。
`tools/toolpaths.json` 已指向本文件（`keys/debug.keystore`），所以**每次构建的证书都相同**。

- 与手机上已安装的 EN 客户端是**同一把 key** → `adb install -r` 可直接覆盖安装
- **不要删除/替换**：换 key 后无法覆盖安装，只能卸载重装（账号可用引継ぎ / 服务端改绑恢复）
- 密码是公开的标准 debug 密码，**不要**用于正式发布渠道
- 私服补丁（lunar-scripts）如需签名，也建议指向本文件，保持全链路一致

手工签名示例：

```bash
zipalign -p -f 4 in.apk aligned.apk
apksigner sign --ks keys/debug.keystore --ks-pass pass:android \
  --ks-key-alias androiddebugkey --out out.apk aligned.apk
apksigner verify --print-certs out.apk     # 证书应等于上表 SHA-256
```
