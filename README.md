# CronWeb

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/d26364e5d2bc4007b91ea241f2ad8272)](https://app.codacy.com/gh/So0ni/cronweb?utm_source=github.com&utm_medium=referral&utm_content=So0ni/cronweb&utm_campaign=Badge_Grade_Settings)

CronWeb是一个不依赖crontab的cron服务，并有一个与之对应的WebUI - [CronWeb-front](https://github.com/So0ni/cronweb-front)

这个项目里已经带上CronWeb-front了，所以你不必再手动去编译(不过有可能自带的版本会忘记更新，能用就行)。

## Features

* 不依赖crontab，这意味着Windows上也能用

* 可以中止正在执行的任务

* 可配置的指数退避错误重试

* 支持推送运行结果的Webhook和本地hook

* 使用sqlite3，不用额外安装数据库(某些情况下也可能是坏处)

* 比较轻量，大部分状况下Linux中内存占用不足50MB(其实就是功能少)

## Warning

为了安全一定要至少确保以下几点(可能仍然不够):

1. 绝对绝对不要使用root用户部署

2. 千万不要执行非可信代码和程序(这点和crontab一样)

3. 如果要将WebAPI暴露到非本机地址，最好使用客户端证书认证，不要依赖自带密码(CronWeb自带的客户端证书认证和反向代理服务器的客户端证书认证并不冲突， 并且建议同时开启)

4. 尽可能开启客户端证书认证，以解决监听本地回环时来自本地的WebAPI非法访问

5. 确保被执行的代码不会被非法修改，CronWeb的配置文件和证书目录不会被其它账户访问

这个服务具有几个安全薄弱环节(或者更多)，使用时请仔细斟酌安全性：

1. 关键WebAPI虽然要求认证，但是为静态密码，且无尝试次数限制(密码甚至在配置文件中都是明文)

2. 并未隔离被执行的代码，执行非可信代码可能会造成严重的安全问题

## Installation

有两种安装办法。(半自动和手动哈哈哈)

### 半自动

使用Python 3.7或以上版本在项目目录执行

```bash
python install.py
```

安装脚本会做以下操作：

1. 生成配置文件 `config.yaml`

2. 如果选择开启客户端证书认证，且本地环境已安装openssl， 则在项目下的`certs/`目录生成服务端证书和客户端CA证书

3. 在项目的 `.venv` 目录生成虚拟环境

4. 为虚拟环境安装依赖

5. 生成子进程环境变量配置 `.env_subprocess.json`

6. 如果使用Linux系统且使用systemd，则会生成`cronweb.service`文件

你需要手动做的是：

1. 确保执行 `install.py` 的Python环境有pip和venv两个依赖包
   (这两个包在Linux原生的Python环境中似乎都需要手动安装)

2. 检查`config.yaml`文件内路径配置或修改

3. 检查`.env_subprocess.json`文件内的环境变量，删除敏感信息

4. 检查`cronweb.service`文件的路径正确性，并将其复制到systemd的目录中，重载systemd

5. 对于非Linux用户例如Windows、MacOS用户， 你需要寻找工具将启动命令封装成服务

#### 环境变量配置和静默安装

`install.py` 脚本提供从环境变量读取配置和静默安装的功能。

```bash
python install.py --config-from-env --docker-mode
```

使用 `python install.py list-config-env` 列出可配置环境变量和已配置环境变量，输出如下:

```
 > python install.py list-config-env
 
[*] 在环境变量中配置过的值
CW_CONFIG_HOST-----------   127.0.0.1
CW_CONFIG_PORT-----------   8000
CW_CONFIG_CLIENT_CERT----   True
CW_CONFIG_SYSTEM---------   Linux
CW_CONFIG_DIR_PROJECT----   ~\cronweb
CW_CONFIG_CONDA_PREFIX---   None
CW_CONFIG_DOCKER_MODE----   False
CW_CONFIG_LOG_DIR--------   ~\cronweb\logs
CW_CONFIG_SECRET--------- * 123456
CW_CONFIG_DB_PATH--------   ~\cronweb\logs.sqlite3
CW_CONFIG_LOG_LEVEL------ * DEBUG
CW_CONFIG_WORK_DIR-------   ~\cronweb\scripts
CW_CONFIG_USER_CURRENT---   fake_user
CW_CONFIG_USER_OPTION----   cronweb
CW_CONFIG_GROUP_OPTION---   cronweb
CW_CONFIG_SSL_KEYFILE----   ~\cronweb\certs\server.key
CW_CONFIG_SSL_CERTFILE---   ~\cronweb\certs\server.pem
CW_CONFIG_SSL_CA_CERTS---   ~\cronweb\certs\client_ca.pem
CW_CONFIG_DIR_VENV-------   ~\cronweb\.venv
CW_CONFIG_BIN_PYTHON-----   None
```

### 手动

手动操作的话，对于半自动安装，除了手动操作部分之外，你还需要：

1. 将template目录下的配置文件模板复制到项目目录下， 并手动修改里面的参数值，最后将文件名修改为config.yaml或cronweb.service

2. 创建一个名为.env_subprocess.json的文件，包含subprocess运行时的环境变量

3. 为你的Python环境安装依赖包

虚拟环境不是必须的，你可以使用venv甚至conda，或者直接不用(大胆)。

### 生成客户端证书

```bash
python install.py gen-user -s <客户端编号> [-k 客户端CA私钥路径] [-c 客户端CA证书路径]
```

如果你并没有自定义或修改过自动生成的客户端CA证书的相关路径，则可省略`-k`和`-c`两个参数。

客户端证书将会生成在项目目录下的dist目录中，每组客户端证书包含四个文件：

* `*.csr` 证书请求文件

* `*.pem` 证书

* `*.key` 证书私钥

* `*.pfx` 包含公钥和私钥的证书文件，可以直接在Windows上导入

> 示例
> `python install.py gen-user -s 01`

## Usage

如果你用了systemd，在复制service文件和重载systemd配置文件之后可以尝试通过执行以下命令启动:

```bash
sudo systemctl start cronweb
```

或者你需要在shell中运行CronWeb(调试):

```bash
# 激活虚拟环境(如果有的话)
python manage.py run
```

因为CronWeb并不包含守护进程，在不包含systemd的其它系统中，你需要通过一些手段来起到守护进程的作用。 例如，Windows中可以借助工具封装成系统服务，MacOS中可以借助`launchd`
，甚至可以借助`supervisor` `pm2`等工具起到守护进程的作用。

### 注意

在命令中使用输入输出重定向应该是可以的，但是输出重定向之后会导致CronWeb过长时间获取不到输出信息，会被认为子进程已经卡死，达到超时时间后会被kill.(无输出超时时间为1800s)

## Webhook

CronWeb支持以Webhook的方式推送运行结果。

### 开启方式

设置配置文件中的`worker.webhook_url`和`worker.webhook_secret`两个配置。

* `worker.webhook_url` 包含http或https前缀

* `worker.webhook_secret` 用于验签，需要保密不可泄漏

### Payload

Webhook以POST的方式请求hook URL，其对应的POST body为json：

```json
{
  "name": "任务名称 str",
  "shot_id": "执行任务的编号 str",
  "state": "任务运行结果 str [DONE | ERROR | KILLED]",
  "job_type": "任务触发类型 str [SCHEDULE | RETRY | MANUAL]",
  "timestamp": "webhook请求时间戳 int 单位:ms"
}
```

### Sign

CronWeb的Webhook的请求中包含名为`X-Cronweb-Token`的头信息，为POST body的签名信息。

#### 验签方式

1. 将`X-Cronweb-Token`头信息base64解码获得二进制签名摘要

2. 用预置webhook密码作为key，将原始二进制POST body以`HMAC-sha256`的方式计算摘要

3. 对比前两步生成的摘要，一致则验签成功

#### 预防可能针对Webhook的攻击

* CronWeb不会对同一个shot_id请求两次或以上，对重复的shot_id请求进行过滤

* 比较载荷和本地时间戳，设定一个安全阈值，丢弃超时的请求

* 设定请求来源ip白名单

* 对webhook使用https

## Local Hooks

CronWeb也支持添加本地代码的hook。CronWeb启动脚本会在启动时扫描并加载符合规则的函数作为hook函数。

> 相比webhook 不要额外建立hook监听服务，例如可以直接在这里面执行消息推送

### 约定规则

1. 项目目录下的`hooks`目录中，以`hook`开头的python脚本文件

2. 以`hook_job_done`开头的异步函数(普通同步函数不会被加载)

3. hook函数签名

```python
import worker


async def hook_job_done_sample(shot_id: str, name: str,
                               state: worker.JobStateEnum,
                               job_type: worker.JobTypeEnum) -> None:
    pass
```

### 注意

1. 不要在hook函数中直接使用阻塞型io，虽然这不会导致定时任务整体延迟，但是却会导致其它hook延迟。使用`asyncio.run_in_executor`

2. 不要在hook函数中直接进行CPU密集型操作，由于GIL的存在，执行CPU密集型操作甚至会等导致主事件循环出现异常。同样使用`asyncio.run_in_executor`

3. hook函数有60s超时限制，超时会被取消执行，需要在hooks函数中捕捉`asyncio.CancelledError`

4. 使用全局变量和并发时注意内存泄露问题

## 通过url-query验证登陆状态

在访问API时，除了在Header中添加对应的字段通过登陆之外，也可以通过url-query中添加token参数来实现登陆状态。

token的生成算法在`web.web_fastapi.WebFastAPI.generate_token`方法中。

## Screenshots

![WebUI 登录页](/assets/ss-login.png)

![WebUI 控制面板](/assets/ss-main.png)

## License

CronWeb and CronWeb-front Copyright (C) 2021. Sonic Young.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
License as published by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <https://www.gnu.org/licenses/>.

