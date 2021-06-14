#!/usr/bin/env python3
import argparse
import os
import pathlib
import sys
import typing
import subprocess


def risk_tips():
    print(
        '你需要明白使用管理员身份运行CronWeb所带来的巨大风险，因为CronWeb本身并没有限制定时任务代码的可操作性，'
        '这意味着如果使用管理员身份运行CronWeb且密码被破解将可能会导致整体管理员权限的失守。\n'
        '请创建一个最小权限的新账户，并使用新账户来运行CronWeb，同时如果需要将API暴露在外网时建议结合'
        '客户端证书认证(仍然可能会有风险，请自行斟酌)'
    )


def check_py_version():
    print('检查Python版本...')
    if sys.version_info < (3, 7):
        print('需要确保使用的Python版本大于等于3.7')
        sys.exit(-1)


def check_secure():
    print('检查安全性...')
    import getpass
    user = getpass.getuser()
    if system == 'Linux' and pathlib.Path('/.dockerenv').exists():
        print('你似乎处于Docker环境中，但是你仍然需要针对Docker进行一些设置以提高安全性')
        return None
    if user == 'root' or user == 'Administrator':
        print('你现在正在以管理员(root或Administrator)身份运行!\n'
              '虽然这个安装程序并不对外暴露任何端口也不会留存任何进程，但是使用管理员权限运行会导致生成的文件'
              '具有管理员身份，请使用非管理员权限账户运行')
        sys.exit(3)


def generate_config_file():
    print('从模板生成配置文件...')
    global client_cert, ssl_keyfile, ssl_certfile, ssl_ca_certs
    file_tmpl_config = dir_project / 'template' / 'config.yaml.tmpl'
    file_config = dir_project / 'config.yaml'
    if file_config.exists():
        yes_or_no = input('配置文件似乎已经存在，需要替换吗?([no], yes): ').strip().lower()
        if yes_or_no != 'yes':
            print(f'你的回答并非yes, 跳过配置文件替换')
            return None

    with open(file_tmpl_config, 'r', encoding='utf8') as fp:
        tmpl_config = fp.read()
    global host, port
    secret = input('输入新的API密码: ').strip()
    host = input('输入API监听主机地址(建议留空为默认127.0.0.1): ').strip() or '127.0.0.1'
    port = int(input('输入API监听主机端口(建议留空为默认8000): ').strip() or 8000)
    db_path = input('输入数据库文件存放路径(留空为默认项目目录下的logs.sqlite3文件): '
                    ).strip() or f'{dir_project / "logs.sqlite3"}'
    log_dir = input('输入子进程日志文件存放路径(留空为默认项目目录下的logs目录): '
                    ).strip() or f'{dir_project / "logs"}'
    log_level = input('输入CronWeb日志等级(留空为默认DEBUG): ').strip() or 'DEBUG'
    work_dir = input('输入任务的工作目录(留空为默认项目目录下scripts目录): '
                     ).strip() or f'{dir_project / "scripts"}'

    yes_or_no = input('启用客户端证书验证吗?([yes], no): ').strip().lower()
    if yes_or_no == 'no':
        client_cert = False
        print('禁用客户端证书验证，你需要确保WebAPI不会被非法访问')
        ssl_keyfile = None
        ssl_certfile = None
        ssl_ca_certs = None
        client_cert = None
    else:
        client_cert = True
        print('启用客户端证书验证')
        ssl_certfile = input('输入服务端证书路径(留空为默认自动生成): '
                             ).strip() or f'{dir_project / "certs" / "server.pem"}'
        ssl_keyfile = input('输入服务端证书私钥路径(留空为默认自动生成): '
                            ).strip() or f'{dir_project / "certs" / "server.key"}'
        ssl_ca_certs = input('输入客户端CA证书路径(留空为默认自动生成): '
                             ).strip() or f'{dir_project / "certs" / "client_ca.pem"}'

    config_str = tmpl_config.format(**{
        'secret': secret, 'host': host, 'port': port,
        'db_path': db_path, 'log_dir': log_dir,
        'log_level': log_level, 'work_dir': work_dir,
        'ssl_cert_reqs': f'ssl_cert_reqs: {2 if client_cert else 0}',
        'ssl_certfile': f"ssl_certfile: '{ssl_certfile}'" if ssl_certfile else '',
        'ssl_keyfile': f"ssl_keyfile: '{ssl_keyfile}'" if ssl_keyfile else '',
        'ssl_ca_certs': f"ssl_ca_certs: '{ssl_ca_certs}'" if ssl_ca_certs else ''
    })
    if not file_config.parent.exists():
        file_config.parent.mkdir(parents=True)

    with open(file_config, 'w', encoding='utf8') as fp:
        fp.write(config_str)

    if client_cert:
        create_certs()


def create_certs():
    if client_cert is not True:
        print('未配置客户端证书加密，跳过证书生成过程')
        return None
    try:
        subprocess.check_call(['openssl', 'version'], stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        print('似乎没有安装openssl，你可能需要手动生成或获取相关证书')
        return None

    file_cert = pathlib.Path(ssl_certfile)
    file_cert_key = pathlib.Path(ssl_keyfile)
    file_ca = pathlib.Path(ssl_ca_certs)
    file_ca_key = file_ca.parent / 'client_ca.key'

    if not file_cert.exists():
        yes_or_no = input('服务端证书不存在，要生成吗?([yes], no): ').strip().lower()
        if yes_or_no != 'no':
            print('生成自签名服务端证书')
            if not file_cert.parent.exists():
                file_cert.parent.mkdir(parents=True)
            try:
                subprocess.check_call([
                    'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-sha256', '-days', '730',
                    '-nodes', '-keyout', f'{file_cert_key}', '-out', f'{file_cert}',
                    '-subj', f'/CN=CronWeb', '-addext',
                    f'subjectAltName=IP:{host}{",DNS:localhost" if host == "127.0.0.1" else ""}'
                ])
                print('服务端自签名证书生成完成\n'
                      f'服务端证书公钥文件路径: {file_cert} \n'
                      f'服务端证书私钥文件路径: {file_cert_key}')

            except subprocess.CalledProcessError:
                print('服务端证书生成失败，你可能需要手动操作')
            print('请保证服务端证书私钥不被泄露，某些情况下你需要手动信任服务器的自签证书')

    if not file_ca.exists():
        yes_or_no = input('客户端CA证书不存在，要生成吗?([yes], no): ').strip().lower()
        if yes_or_no != 'no':
            print('生成客户端CA证书')
            if not file_ca.parent.exists():
                file_ca.parent.mkdir(parents=True)
            try:
                subprocess.check_call([
                    'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-sha256', '-days', '730',
                    '-nodes', '-keyout', f'{file_ca_key}', '-out', f'{file_ca}',
                    '-subj', f'/CN=CronWebClientCA'
                ])
                print('客户端自签名CA证书生成完成\n'
                      f'客户端CA证书公钥文件路径: {file_ca} \n'
                      f'客户端CA证书私钥文件路径: {file_ca_key}')

            except subprocess.CalledProcessError:
                print('CA证书生成失败，你可能需要手动操作')
            print('请保证客户端CA证书私钥不被泄露')


def create_venv():
    print('生成虚拟环境...')
    import venv
    global dir_venv, bin_python
    dir_venv = dir_project / '.venv'
    if system == 'Windows':
        bin_python = dir_venv / 'Scripts' / 'python.exe'
    else:
        bin_python = dir_venv / 'bin' / 'python'

    if dir_venv.exists():
        print('虚拟环境已存在，跳过生成')
        return None
    venv.create(dir_venv, with_pip=True)


def install_pkg():
    print('安装必要依赖...')
    if not bin_python.exists():
        print(f'{bin_python}不存在 退出')
        sys.exit(3)
    file_req = dir_project / 'requirements.txt'
    subprocess.check_call([str(bin_python), '-m', 'pip', 'install', '-r', str(file_req)])


def generate_env_subprocess():
    print('生成运行环境配置文件...')
    import json
    env_source = dict(os.environ)
    env_source['VIRTUAL_ENV'] = str(dir_venv)
    env_source.pop('PYTHONHOME', None)
    if system == 'Windows':
        env_source['PATH'] = f"{bin_python.parent};{env_source['PATH']}"
    else:
        env_source['PATH'] = f"{bin_python.parent}:{env_source['PATH']}"
    path_env_file = dir_project / '.env_subprocess.json'
    if path_env_file.exists():
        yes_or_no = input('环境文件似乎已经存在，需要替换吗?([no], yes): ').strip().lower()
        if yes_or_no != 'yes':
            print(f'你的回答并非yes, 跳过环境文件替换')
            return None
    with open(path_env_file, 'w', encoding='utf8') as fp:
        json.dump(env_source, fp, ensure_ascii=False, indent=4)


def common_operation():
    check_py_version()
    risk_tips()
    generate_config_file()
    create_venv()
    install_pkg()
    generate_env_subprocess()


# 系统操作

def before_linux():
    print('检查环境要求...')

    def check_venv():
        failed_list = []
        try:
            import venv
        except ModuleNotFoundError:
            failed_list.append('venv')
            pass
        try:
            import pip
        except ModuleNotFoundError:
            failed_list.append('pip')
            pass
        if failed_list:
            print(f'当前Python环境没有安装{failed_list}，请安装后重试')
            sys.exit(3)

    check_venv()


def before_windows():
    pass


def before_macos():
    pass


# 善后

def after_linux():
    def check_systemd():
        out = subprocess.check_output(['ps', '--no-headers', '-o', 'comm', '1']).decode().strip()
        if 'systemd' not in out:
            print('当前系统并未使用systemd，不需要生成service文件')
            sys.exit(3)

    def generate_service_unit():
        file_tmpl_service = dir_project / 'template' / 'cronweb.service.tmpl'
        with open(file_tmpl_service, 'r', encoding='utf8') as fp:
            tmpl_service = fp.read()
        global user, group
        import getpass
        user = input('输入用于运行CronWeb的用户的用户名(默认为当前用户): ').strip() or getpass.getuser()
        group = user
        command = f'{bin_python.absolute()} {dir_project.absolute() / "manage.py"} run'
        pwd = str(dir_project)
        service_str = tmpl_service.format(user=user, group=group, exec=command, pwd=pwd)
        file_service = dir_project / 'cronweb.service'
        with open(file_service, 'w', encoding='utf8') as fp:
            fp.write(service_str)

        try:
            import pwd
            pwd.getpwnam(user)
        except KeyError:
            yes_or_no = input(f'用户{user}不存在，你想要创建吗?你需要有对应的sudo权限([yes], no)'
                              ).strip().lower()
            if yes_or_no == 'yes':
                os.system(f'sudo useradd {user}')
                import getpass
                current_group = getpass.getuser()
                os.system(f'sudo usermod -a -G {current_group} {user}')
            else:
                print('你的回答并非yes，跳过用户创建，你需要手动创建用户并处理对应日志文件的读写权限')
            pass
        print('你需要手动把service文件复制到systemd的目录中，并重载systemd')

    check_systemd()
    generate_service_unit()


def after_windows():
    pass


def after_macos():
    pass


def route():
    import platform

    global system
    system = platform.system()

    if system == 'Linux':
        before_linux()
        common_operation()
        after_linux()
    elif system == 'Windows':
        before_windows()
        common_operation()
        after_windows()
    elif system == 'Darwin':
        before_macos()
        common_operation()
        after_macos()
    else:
        print(f'对于当前系统你可能需要手动进行配置{system}')
        sys.exit(3)


def gen_user_cert(
        path_key: typing.Optional[typing.Union[str, pathlib.Path]],
        path_cert: typing.Optional[typing.Union[str, pathlib.Path]],
        serial: str
):
    path_key = pathlib.Path(path_key) if path_key else (dir_project / 'certs' / 'client_ca.key')
    path_cert = pathlib.Path(path_cert) if path_cert else (dir_project / 'certs' / 'client_ca.pem')
    if not path_key.exists() or not path_cert.exists():
        raise FileNotFoundError('客户端CA证书私钥或公钥不存在')

    try:
        subprocess.check_call(['openssl', 'version'], stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        print('似乎没有安装openssl，你可能需要手动生成客户端证书')
        return None

    path_user_cert = dir_project / 'dist' / f'user_{serial}.pem'
    path_user_key = dir_project / 'dist' / f'user_{serial}.key'
    path_user_csr = dir_project / 'dist' / f'user_{serial}.csr'
    path_user_pfx = dir_project / 'dist' / f'user_{serial}.pfx'

    if not path_user_cert.parent.exists():
        path_user_cert.parent.mkdir(parents=True)

    print('生成客户端证书私钥')
    subprocess.check_call([
        'openssl', 'genrsa', '-out', str(path_user_key), '2048'
    ])

    print('生成客户端证书公钥')
    subprocess.check_call([
        'openssl', 'req', '-new', '-key', str(path_user_key),
        '-out', str(path_user_csr), '-subj', f'/CN=CronWeb_user_{serial}'
    ])
    subprocess.check_call([
        'openssl', 'x509', '-req', '-days', '365',
        '-in', str(path_user_csr), '-out', str(path_user_cert),
        '-CAkey', str(path_key), '-CA', str(path_cert), '-set_serial', serial
    ])

    print('生成pfx证书')
    password = input('输入pfx证书密码(不建议留空): ').strip()
    subprocess.check_call([
        'openssl', 'pkcs12', '-export',
        '-out', str(path_user_pfx), '-inkey', str(path_user_key),
        '-in', str(path_user_cert), '-certfile', str(path_cert),
        '-password', f'pass:{password}'
    ])

    print('客户端证书生成完成，请保护好生成的客户端证书')


if __name__ == '__main__':
    global dir_project
    dir_project = pathlib.Path(__file__).parent.absolute()

    parser = argparse.ArgumentParser(description='CronWeb安装工具')
    parser.add_argument('command', nargs='?', type=str, help='生成服务证书',
                        choices=['gen-user']
                        )
    parser.add_argument('-s', '--serial', nargs='?', type=str, default=None,
                        help='指定生成的客户端证书序号')
    parser.add_argument('-k', '--ca-key', nargs='?', type=str,
                        default=None,
                        help='客户端CA证书公钥路径(默认为certs/client_ca.pem)')
    parser.add_argument('-c', '--ca-cert', nargs='?', type=str,
                        default=None,
                        help='客户端CA证书私钥路径(默认为cert/client_ca.key)')
    args = parser.parse_args()
    print(args)

    if args.command is None:
        route()
    elif args.command == 'gen-user':
        gen_user_cert(args.ca_key, args.ca_cert, args.serial)
