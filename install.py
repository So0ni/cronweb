#!/usr/bin/env python3
import os
import sys


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
    if user == 'root' or user == 'Administrator':
        print('你现在正在以管理员(root或Administrator)身份运行!\n'
              '虽然这个安装程序并不对外暴露任何端口也不会留存任何进程，但是使用管理员权限运行会导致生成的文件'
              '具有管理员身份，请使用非管理员权限账户运行')
        sys.exit(3)


def generate_config_file():
    print('从模板生成配置文件...')
    file_tmpl_config = dir_project / 'template' / 'config.yaml.tmpl'
    with open(file_tmpl_config, 'r', encoding='utf8') as fp:
        tmpl_config = fp.read()
    secret = input('输入新的API密码: ').strip()
    host = input('输入API监听主机地址(建议留空为默认127.0.0.1): ').strip() or '127.0.0.1'
    port = int(input('输入API监听主机端口(建议留空为默认8000): ').strip() or 8000)
    db_path = input('输入数据库文件存放路径(留空为默认项目目录下的logs.sqlite3文件): '
                    ).strip() or f'{dir_project / "logs.sqlite3"}'
    log_dir = input('输入子进程日志文件存放路径(留空为默认项目目录下的logs目录): '
                    ).strip() or f'{dir_project / "logs"}'
    log_level = input('输入CronWeb日志等级(留空为默认DEBUG): ').strip() or 'DEBUG'
    config_str = tmpl_config.format(**{
        'secret': secret, 'host': host, 'port': port,
        'db_path': db_path, 'log_dir': log_dir,
        'log_level': log_level
    })
    file_config = dir_project / 'config.yaml'
    if not file_config.parent.exists():
        file_config.parent.mkdir(parents=True)

    if file_config.exists():
        yes_or_no = input('配置文件似乎已经存在，需要替换吗?(yes, no): ').strip().lower()
        if yes_or_no != 'yes':
            print(f'你的回答并非yes, 跳过配置文件替换')
            return None

    with open(file_config, 'w', encoding='utf8') as fp:
        fp.write(config_str)


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
    import subprocess
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
        yes_or_no = input('环境文件似乎已经存在，需要替换吗?(yes, no): ').strip().lower()
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
        import subprocess
        out = subprocess.check_output(['ps', '--no-headers', '-o', 'comm', '1']).decode().strip()
        if 'systemd' not in out:
            print('当前系统并未使用systemd，不需要生成service文件')
            sys.exit(3)

    def generate_service_unit():
        file_tmpl_service = dir_project / 'template' / 'cronweb.service.tmpl'
        with open(file_tmpl_service, 'r', encoding='utf8') as fp:
            tmpl_service = fp.read()
        global user, group
        user = input('输入用于运行CronWeb的用户的用户名(默认为cronweb): ').strip() or 'cronweb'
        group = user
        command = f'{bin_python.absolute()} {dir_project.absolute() / "manage.py"} run'
        service_str = tmpl_service.format(user=user, group=group, exec=command)
        file_service = dir_project / 'cronweb.service'
        with open(file_service, 'w', encoding='utf8') as fp:
            fp.write(service_str)

        try:
            import pwd
            pwd.getpwnam(user)
        except KeyError:
            yes_or_no = input(f'用户{user}不存在，你想要创建吗?你需要有对应的sudo权限(yes, no)').strip().lower()
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
    from pathlib import Path

    global system, dir_project
    system = platform.system()
    dir_project = Path(__file__).parent

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


if __name__ == '__main__':
    route()
