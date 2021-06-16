# CronWeb

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/d26364e5d2bc4007b91ea241f2ad8272)](https://app.codacy.com/gh/So0ni/cronweb?utm_source=github.com&utm_medium=referral&utm_content=So0ni/cronweb&utm_campaign=Badge_Grade_Settings)

CronWeb是一个不依赖crontab的cron服务，并有一个与之对应的WebUI - [CronWeb-front](https://github.com/So0ni/cronweb-front)

这个项目里已经带上CronWeb-front了，所以你不必再手动去编译(不过有可能自带的版本会忘记更新，能用就行)。

## Features

* 不依赖crontab，这意味着Windows上也能用

* 可以中止正在执行的任务

* 比较轻量(其实就是功能少)

## Warning

为了安全一定要至少确保以下几点(可能仍然不够):

1. 绝对绝对不要使用root用户部署

2. 千万不要执行非可信代码和程序(这点和crontab一样)

3. 如果要将WebAPI暴露到非本机地址，最好使用客户端证书认证，
   不要依赖自带密码(CronWeb自带的客户端证书认证和反向代理服务器的客户端证书认证并不冲突，
   并且建议同时开启)
   
4. ~即使只监听本地回环，本机其它账户仍然可以通过回环地址访问到WebAPI，~
   ~所以请不要在可能有非可信人员访问到哪怕另外账户的服务器或计算机上部署~
   尽可能开启客户端证书认证，以解决监听本地回环时来自本地的WebAPI非法访问
   
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

2. 如果选择开启客户端证书认证，且本地环境已安装openssl，
   则在项目下的`certs/`目录生成服务端证书和客户端CA证书

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

5. 对于非Linux用户例如Windows、MacOS用户，
   你需要寻找工具将启动命令封装成服务

### 手动

手动操作的话，对于半自动安装，除了手动操作部分之外，你还需要：

1. 将template目录下的配置文件模板复制到项目目录下，
并手动修改里面的参数值，最后将文件名修改为config.yaml或cronweb.service
   
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
## Todo

- 错误重试

## Screenshots

![WebUI 登录页](/assets/ss-login.png)

![WebUI 控制面板](/assets/ss-main.png)

## License

CronWeb and CronWeb-front
Copyright (C) 2021. Sonic Young.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

