# 进展填报系统

本地运行地址：

```text
http://127.0.0.1:8765
```

## 启动方式

双击 `run.bat`，或在当前目录执行：

```powershell
python app.py
```

局域网或服务器运行时可以指定监听地址和端口：

```powershell
$env:HOST="0.0.0.0"
$env:PORT="8765"
$env:ADMIN_PASSWORD="你的管理员密码"
python app.py
```

## 初始数据

- 用户：张三、李四、王五
- 项目：A、B、C
- 每个项目默认包含任务1到任务9
- 每个任务默认工作量为 10

## 管理员

- 初始密码：`admin123`
- 管理员端可以维护人员、项目、任务、工作量、任务启停，并确认/修正任务最终进度。
- Excel 导出按钮在管理员登录后可用。

## 数据文件

系统数据保存在：

```text
progress.db
```

每次项目进展和科研进展提交都会保留历史记录。

## 云端部署环境变量

- `HOST`：云平台通常设为 `0.0.0.0`
- `PORT`：多数云平台会自动注入
- `ADMIN_PASSWORD`：首次创建数据库时写入的管理员初始密码
- `DATA_DIR`：持久化数据目录，例如 `/var/data`
- `DB_PATH`：可选，完整数据库路径，例如 `/var/data/progress.db`

注意：如果数据库已经存在，修改 `ADMIN_PASSWORD` 不会覆盖数据库里的管理员密码。需要进入管理员端修改，或删除旧数据库重新初始化。

## Render 部署

项目已经包含 `render.yaml`，可用 Render Blueprint 部署。

推荐配置：

- Service type：Web Service
- Runtime：Python
- Build Command：`pip install -r requirements.txt`
- Start Command：`python app.py`
- Persistent Disk mount path：`/var/data`
- Disk size：`1 GB`
- Environment variables：
  - `HOST=0.0.0.0`
  - `DATA_DIR=/var/data`
  - `ADMIN_PASSWORD=你的管理员密码`

如果使用 Blueprint，Render 会读取 `render.yaml` 并提示填写 `ADMIN_PASSWORD`。
