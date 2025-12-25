# 焕新社区 S3 对象存储 rclone 配置教程

## 1. 下载并安装 rclone

### 1.1 检查系统架构

```bash
uname -m
```

根据输出选择对应版本：
| 输出 | 下载版本 |
|------|----------|
| `aarch64` | linux-arm64 |
| `x86_64` | linux-amd64 |

### 1.2 下载 rclone

**ARM64 架构（如焕新社区服务器）：**
```bash
cd ~/work
wget https://github.com/rclone/rclone/releases/download/v1.68.2/rclone-v1.68.2-linux-arm64.zip
```

**x86_64 架构：**
```bash
cd ~/work
wget https://github.com/rclone/rclone/releases/download/v1.68.2/rclone-v1.68.2-linux-amd64.zip
```

### 1.3 解压并安装

```bash
# ARM64
unzip rclone-v1.68.2-linux-arm64.zip
cd rclone-v1.68.2-linux-arm64

# 复制到系统目录
cp rclone /usr/bin/
chmod +x /usr/bin/rclone

# 验证安装
rclone version
```

---

## 2. 获取 S3 凭证

在焕新社区控制台中：

1. 进入 **资产管理** → **文件管理**
2. 点击 **查看使用方式**
3. 记录以下信息：
   - **Endpoint**: `https://nm.aihuanxin.cn`
   - **Access Key ID**: 你的访问密钥 ID
   - **Secret Access Key**: 你的秘密访问密钥（点击复制图标获取）

---

## 3. 配置 rclone

### 方法一：直接创建配置文件（推荐）

```bash
mkdir -p /root/.config/rclone

cat > /root/.config/rclone/rclone.conf << 'EOF'
[nm-aihuanxin]
type = s3
provider = Minio
access_key_id = 你的AccessKeyID
secret_access_key = 你的SecretAccessKey
endpoint = https://nm.aihuanxin.cn
acl = private
EOF
```

**示例：**
```bash
cat > /root/.config/rclone/rclone.conf << 'EOF'
[nm-aihuanxin]
type = s3
provider = Minio
access_key_id = qAu2hO9z
secret_access_key = lEv8Tu6oYO
endpoint = https://nm.aihuanxin.cn
acl = private
EOF
```

### 方法二：交互式配置

```bash
rclone config
```

按以下步骤操作：
1. `n` - 新建远程
2. 输入名称：`nm-aihuanxin`
3. 选择 `4` (s3)
4. 选择 `19` (Minio)
5. 选择 `1` (手动输入凭证)
6. 输入 Access Key ID
7. 输入 Secret Access Key
8. 选择 `1` (v4 签名)
9. 输入 Endpoint: `https://nm.aihuanxin.cn`
10. 其余选项按 Enter 使用默认值
11. `y` 确认保存
12. `q` 退出

---

## 4. 使用 rclone

### 4.1 查看存储桶列表

```bash
rclone lsd nm-aihuanxin:
```

### 4.2 查看存储桶内容

```bash
rclone ls nm-aihuanxin:你的存储桶名称/
```

### 4.3 上传文件/文件夹

```bash
# 上传文件夹
rclone copy /本地路径/ nm-aihuanxin:存储桶名称/目标路径/

# 示例
rclone copy /root/work/ALPHAQUBIT nm-aihuanxin:jtdlp-3ed7854b946a47b1a49ad754baa76cd3/
```

### 4.4 下载文件/文件夹

```bash
rclone copy nm-aihuanxin:存储桶名称/路径/ /本地路径/
```

### 4.5 同步（双向保持一致）

```bash
rclone sync /本地路径/ nm-aihuanxin:存储桶名称/路径/
```

### 4.6 显示传输进度

```bash
rclone copy -P /本地路径/ nm-aihuanxin:存储桶名称/路径/
```

---

## 5. 常用参数

| 参数 | 说明 |
|------|------|
| `-P` | 显示进度 |
| `-v` | 详细输出 |
| `--dry-run` | 模拟运行，不实际传输 |
| `--transfers 4` | 并行传输数（默认4） |
| `--exclude "*.tmp"` | 排除文件 |

---

## 6. 常见问题

### Q: 提示 "Exec format error"
A: 下载了错误架构的版本，用 `uname -m` 检查并下载正确版本。

### Q: 提示 "secret_access_key not found"
A: 配置时漏填了 Secret Access Key，重新配置或编辑配置文件添加。

### Q: 提示 "didn't find section in config file"
A: 配置文件不存在或远程名称错误，运行 `rclone config` 创建配置。

---

## 7. 配置文件位置

```
/root/.config/rclone/rclone.conf
```

查看配置：
```bash
cat /root/.config/rclone/rclone.conf
```
