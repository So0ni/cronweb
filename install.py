#!/usr/bin/env python3
import os
import sys
import json
import typing
import getpass
import pathlib
import platform
import argparse
import subprocess

try:
    import dataclasses
except ModuleNotFoundError:
    print('需要确保使用的Python版本大于等于3.7')
    sys.exit(3)

try:
    import pip
    import venv
except ModuleNotFoundError:
    print('需要已安装pip和venv')
    sys.exit(3)

ENV_CONFIG_PREFIX = 'CW_CONFIG_'
PATH_PROJ_ROOT = pathlib.Path(__file__).parent.absolute()


@dataclasses.dataclass
class InfoConfig:
    host: str = '127.0.0.1'
    port: int = 8000
    client_cert: bool = True
    system: str = platform.system()
    dir_project: pathlib.Path = PATH_PROJ_ROOT
    conda_prefix: typing.Optional[pathlib.Path] = pathlib.Path(os.environ.get('CONDA_PREFIX')) if \
        os.environ.get('CONDA_PREFIX') else None
    docker_mode: bool = pathlib.Path('/.dockerenv').exists()
    log_dir: str = f'{PATH_PROJ_ROOT / "logs/"}'
    secret: str = ''
    db_path: str = f'{PATH_PROJ_ROOT / "logs.sqlite3"}'
    log_level: str = 'DEBUG'
    work_dir: str = f'{PATH_PROJ_ROOT / "scripts"}'
    user_current: str = getpass.getuser()
    user_option: str = 'cronweb'
    group_option: str = 'cronweb'
    ssl_keyfile: pathlib.Path = (PATH_PROJ_ROOT / "certs" / "server.key")
    ssl_certfile: pathlib.Path = (PATH_PROJ_ROOT / "certs" / "server.pem")
    ssl_ca_certs: pathlib.Path = (PATH_PROJ_ROOT / "certs" / "client_ca.pem")
    ssl_ca_keyfile: pathlib.Path = (PATH_PROJ_ROOT / "certs" / "client_ca.key")
    client_nginx_certs: pathlib.Path = (PATH_PROJ_ROOT / "certs" / "client_nginx.pem")
    client_nginx_key: pathlib.Path = (PATH_PROJ_ROOT / "certs" / "client_nginx.key")
    dir_venv: pathlib.Path = (PATH_PROJ_ROOT / ".venv/")
    path_config: pathlib.Path = (PATH_PROJ_ROOT / 'config.yaml')
    path_config_tmpl: pathlib.Path = (PATH_PROJ_ROOT / 'template' / 'config.yaml.tmpl')
    path_systemd_unit: pathlib.Path = (PATH_PROJ_ROOT / 'cronweb.service')
    path_systemd_unit_tmpl: pathlib.Path = (PATH_PROJ_ROOT / 'template' / 'cronweb.service.tmpl')
    path_nginx_conf_tmpl: pathlib.Path = (PATH_PROJ_ROOT / 'template' / 'cronweb_nginx.conf.tmpl')
    path_nginx_conf: pathlib.Path = (PATH_PROJ_ROOT / 'cronweb_nginx.conf')
    dir_client_cert_gen: pathlib.Path = (PATH_PROJ_ROOT / 'dist')
    password_pfx: str = ''

    bin_python: typing.Optional[pathlib.Path] = None


def get_env_name(target: str) -> str:
    return f'{ENV_CONFIG_PREFIX}{target.upper()}'


def set_config_from_env(config: InfoConfig) -> None:
    type_hints = typing.get_type_hints(config)
    for attr in config.__dict__.keys():
        value_origin = getattr(config, attr)
        env_name = get_env_name(attr)
        if isinstance(type_hints[attr], typing._GenericAlias):
            var_type = type_hints[attr].__args__[0]
        else:
            var_type = type_hints[attr]
        value = os.environ.get(env_name, None)
        setattr(config, attr, var_type(value) if value is not None else value_origin)


def yes_or_no(prompt: str, default_choice: str,
              config: typing.Optional[InfoConfig] = None) -> bool:
    """yes总是True  no总是False"""
    assert default_choice in {'yes', 'no'}
    default_value = True if default_choice == 'yes' else False
    if config is not None and config.docker_mode is True:
        return default_value
    hint_choice = ('([yes], no) ' if default_value else '([no], yes) ')
    prompt = f'{prompt} {hint_choice}'
    while True:
        choice = input(prompt).strip().lower()
        if not choice:
            return default_value
        if choice in {'yes', 'no'}:
            return True if choice == 'yes' else False
        print('只接受yes, no两个选项')


T = typing.TypeVar('T')


def input_default(prompt: str, default: T, return_type: typing.Type[T] = str,
                  config: typing.Optional[InfoConfig] = None,
                  target: typing.Optional[str] = None) -> T:
    if config is not None:
        if target and not hasattr(config, target):
            raise AttributeError(f'{type(config).__name__} object has no attribute {target}')
        if config.docker_mode is True:
            if target:
                if getattr(config, target) is not None:
                    return getattr(config, target)
                setattr(config, target, default)
            return default
    hint_default = f'[{default}]' if default else ''
    string_input = input(f'{prompt}{hint_default}: ').strip() or default
    value: T = return_type(string_input)
    if config is not None:
        setattr(config, target, value)
    return value


def risk_tips() -> None:
    print(
        '你需要明白使用管理员身份运行CronWeb所带来的巨大风险，因为CronWeb本身并没有限制定时任务代码的可操作性，'
        '这意味着如果使用管理员身份运行CronWeb且密码被破解将可能会导致整体管理员权限的失守。\n'
        '请创建一个最小权限的新账户，并使用新账户来运行CronWeb，同时如果需要将API暴露在外网时建议结合'
        '客户端证书认证(仍然可能会有风险，请自行斟酌)'
    )


def check_secure(config: InfoConfig):
    print('检查安全性...')
    config.user_current = getpass.getuser()
    if config.system == 'Linux' and config.docker_mode:
        print('你似乎处于Docker环境中，但是你仍然需要针对Docker进行一些设置以提高安全性')
        return None
    if config.user_current == 'root' or config.user_current == 'Administrator':
        print('你现在正在以管理员(root或Administrator)身份运行!\n'
              '虽然这个安装程序并不对外暴露任何端口也不会留存任何进程，但是使用管理员权限运行会导致生成的文件'
              '具有管理员身份，请使用非管理员权限账户运行')
        sys.exit(3)


def generate_config_file(config: InfoConfig):
    print('从模板生成配置文件...')

    if config.path_config.exists():
        if not yes_or_no('配置文件似乎已经存在，需要替换吗?: ', 'no', config=config):
            print('跳过配置文件替换')
            return None

    with open(config.path_config_tmpl, 'r', encoding='utf8') as fp:
        tmpl_config = fp.read()
    input_default('输入新的API密码',
                  default=config.secret,
                  config=config, target='secret')
    input_default(f'输入API监听主机地址',
                  default=config.host,
                  config=config, target='host')
    input_default(f'输入API监听主机端口',
                  default=config.port,
                  return_type=int, config=config, target='port')
    input_default('输入数据库文件存放路径',
                  default=config.db_path,
                  config=config, target='db_path')
    input_default('输入子进程日志文件存放路径',
                  default=config.log_dir,
                  config=config, target='log_dir')
    input_default('输入CronWeb日志等级',
                  default=config.log_level,
                  config=config, target='log_level')
    input_default('输入任务的工作目录',
                  default=config.work_dir,
                  config=config, target='work_dir')

    if yes_or_no('启用客户端证书验证吗?', 'yes', config=config):
        config.client_cert = True
        print('启用客户端证书验证')
        input_default('输入服务端证书路径',
                      default=config.ssl_certfile,
                      return_type=pathlib.Path,
                      config=config, target='ssl_certfile')
        input_default('输入服务端证书私钥路径',
                      default=config.ssl_keyfile,
                      return_type=pathlib.Path,
                      config=config, target='ssl_keyfile')
        input_default('输入客户端CA证书路径',
                      default=config.ssl_ca_certs,
                      return_type=pathlib.Path,
                      config=config, target='ssl_ca_certs')
    else:
        config.client_cert = False
        print('禁用客户端证书验证，你需要确保WebAPI不会被非法访问')

    config_str = tmpl_config.format(**{
        'secret': config.secret, 'host': config.host, 'port': config.port,
        'db_path': config.db_path, 'log_dir': config.log_dir,
        'log_level': config.log_level, 'work_dir': config.work_dir,
        'ssl_cert_reqs': 2 if config.client_cert else 0,
        'ssl_certfile': config.ssl_certfile or '',
        'ssl_keyfile': config.ssl_keyfile or '',
        'ssl_ca_certs': config.ssl_ca_certs or ''
    })
    if not config.path_config.parent.exists():
        config.path_config.parent.mkdir(parents=True)

    with open(config.path_config, 'w', encoding='utf8') as fp:
        fp.write(config_str)

    if config.client_cert:
        create_certs(config)


def create_certs(config: InfoConfig):
    if not check_openssl(config):
        print('似乎没有安装openssl，你可能需要手动生成或获取相关证书')
        return None

    file_cert = config.ssl_certfile
    file_cert_key = config.ssl_keyfile
    file_ca = config.ssl_ca_certs
    file_ca_key = file_ca.parent / 'client_ca.key'

    if not file_cert.exists():
        if yes_or_no('服务端证书不存在，要生成吗?', 'yes', config=config):
            print('生成自签名服务端证书')
            if not file_cert.parent.exists():
                file_cert.parent.mkdir(parents=True)
            try:
                subprocess.check_call([
                    'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-sha256', '-days', '730',
                    '-nodes', '-keyout', f'{file_cert_key}', '-out', f'{file_cert}',
                    '-subj', f'/CN=CronWebServer', '-addext',
                    f'subjectAltName=IP:{config.host}'
                ])
                print('服务端自签名证书生成完成\n'
                      f'服务端证书公钥文件路径: {file_cert} \n'
                      f'服务端证书私钥文件路径: {file_cert_key}')

            except subprocess.CalledProcessError:
                print('服务端证书生成失败，你可能需要手动操作')
            print('请保证服务端证书私钥不被泄露，某些情况下你需要手动信任服务器的自签证书')
    print('服务器证书私钥和客户端CA证书私钥是绝密的，无论如何都不要泄露')

    if not file_ca.exists():
        if yes_or_no('客户端CA证书不存在，要生成吗?', 'yes', config=config):
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


def create_venv(config: InfoConfig):
    print('生成虚拟环境...')
    if config.system == 'Windows':
        config.bin_python = config.dir_venv / 'Scripts' / 'python.exe'
    else:
        config.bin_python = config.dir_venv / 'bin' / 'python'

    if config.dir_venv.exists():
        print('虚拟环境已存在，跳过生成')
        return None
    venv.create(config.dir_venv, with_pip=True)


def install_pkg(config: InfoConfig):
    print('安装必要依赖...')
    if not config.bin_python.exists():
        print(f'{config.bin_python}不存在 退出')
        sys.exit(3)
    file_req = config.dir_project / 'requirements.txt'
    subprocess.check_call([str(config.bin_python), '-m', 'pip', 'install', '-r', str(file_req)])


def generate_env_subprocess(config: InfoConfig):
    print('生成运行环境配置文件...')
    path_env_file = config.dir_project / '.env_subprocess.json'
    if path_env_file.exists():
        if not yes_or_no('环境文件似乎已经存在，需要替换吗?', 'no', config=config):
            print('跳过环境文件替换')
            return None

    env_source = dict(os.environ)
    env_source['VIRTUAL_ENV'] = str(config.dir_venv)
    env_source.pop('PYTHONHOME', None)
    if config.system == 'Windows':
        env_source['PATH'] = f"{config.bin_python.parent};{env_source['PATH']}"
    else:
        env_source['PATH'] = f"{config.bin_python.parent}:{env_source['PATH']}"

    for key in tuple(env_source.keys()):
        if key.startswith(ENV_CONFIG_PREFIX):
            env_source.pop(key)

    with open(path_env_file, 'w', encoding='utf8') as fp:
        json.dump(env_source, fp, ensure_ascii=False, indent=4)


def check_openssl(config: InfoConfig) -> bool:
    try:
        subprocess.check_call(['openssl', 'version'], stdout=subprocess.DEVNULL)
        conda_prefix = os.environ.get('CONDA_PREFIX', None)
        if conda_prefix and config.system == 'Windows':
            openssl_conf = pathlib.Path(conda_prefix) / 'Library/openssl.cnf'
            if openssl_conf.exists():
                os.environ['OPENSSL_CONF'] = str(openssl_conf)
        return True
    except FileNotFoundError:
        return False


def common_operation(config: InfoConfig):
    risk_tips()
    generate_config_file(config)
    create_venv(config)
    install_pkg(config)
    generate_env_subprocess(config)


# 系统操作

def before_linux(config: InfoConfig):
    pass


def before_windows(config: InfoConfig):
    pass


def before_macos(config: InfoConfig):
    pass


# 善后

def after_linux(config: InfoConfig):
    def check_systemd():
        out = subprocess.check_output(['ps', '--no-headers', '-o', 'comm', '1']).decode().strip()
        if 'systemd' not in out:
            print('当前系统并未使用systemd，不需要生成service文件')
            return False
        else:
            return True

    def generate_nginx_conf():
        try:
            subprocess.check_call(['nginx', '-v'])
        except FileNotFoundError:
            print('当前系统并未安装nginx，不需要生成service文件')
            return None
        print('生成nginx配置文件')
        with open(config.path_nginx_conf_tmpl, 'r', encoding='utf8') as fp:
            tmpl_nginx = fp.read()
        input_default('输入nginx的反代地址',
                      default=config.host,
                      config=config, target='host')
        input_default('输入nginx的反代端口',
                      default=config.port,
                      config=config, target='port')
        input_default('输入nginx的服务端证书路径',
                      default=config.ssl_certfile,
                      config=config, target='ssl_certfile')
        input_default('输入nginx的服务端证书私钥路径',
                      default=config.ssl_keyfile,
                      config=config, target='ssl_keyfile')
        input_default('输入nginx的客户端认证CA证书路径',
                      default=config.ssl_ca_certs,
                      config=config, target='ssl_ca_certs')
        input_default('输入nginx的客户端认证CA证书路径',
                      default=config.ssl_ca_certs,
                      config=config, target='ssl_ca_certs')
        client_nginx_cert = input_default('输入CronWeb的客户端证书路径',
                                          default=config.ssl_ca_certs.parent / 'client_nginx.pem',
                                          config=config)
        client_nginx_key = input_default('输入CronWeb的客户端证书私钥路径',
                                         default=config.ssl_ca_certs.parent / 'client_nginx.key',
                                         config=config)
        conf_nginx = tmpl_nginx.format(
            ssl_certfile=config.ssl_certfile, ssl_keyfile=config.ssl_keyfile,
            ssl_ca_certs=config.ssl_ca_certs, port=config.port, host=config.host,
            client_nginx_cert=client_nginx_cert, client_nginx_key=client_nginx_key
        )
        with open(config.path_nginx_conf, 'w', encoding='utf8') as fp:
            fp.write(conf_nginx)

    def generate_service_unit():
        if not check_systemd():
            return None
        print('生成systemd service文件')
        with open(config.path_systemd_unit_tmpl, 'r', encoding='utf8') as fp:
            tmpl_service = fp.read()

        input_default('输入用于运行CronWeb的用户的用户名',
                      default=config.user_option,
                      config=config, target='user_option')
        config.group_option = config.user_option
        command = f'{config.bin_python.absolute()} {config.dir_project.absolute() / "manage.py"} run'

        service_str = tmpl_service.format(user=config.user_option, group=config.group_option,
                                          exec=command, pwd=str(config.dir_project),
                                          path_config=str(config.path_config))

        with open(config.path_systemd_unit, 'w', encoding='utf8') as fp:
            fp.write(service_str)

        try:
            import pwd
            pwd.getpwnam(config.user_option)
        except KeyError:
            if yes_or_no(f'用户{config.user_option}不存在，你想要创建吗?你需要有对应的sudo权限: ', 'yes', config=config):
                os.system(f'sudo useradd {config.user_option}')
                current_group = config.user_current
                os.system(f'sudo usermod -a -G {current_group} {config.user_option}')
            else:
                print('你需要手动创建用户并处理对应日志文件的读写权限')
            pass
        print('你需要手动把service文件复制到systemd的目录中，并重载systemd')

    generate_service_unit()
    generate_nginx_conf()


def after_windows(config: InfoConfig):
    pass


def after_macos(config: InfoConfig):
    pass


def route(config: InfoConfig):
    if config.system == 'Linux':
        before_linux(config)
        common_operation(config)
        after_linux(config)
    elif config.system == 'Windows':
        before_windows(config)
        common_operation(config)
        after_windows(config)
    elif config.system == 'Darwin':
        before_macos(config)
        common_operation(config)
        after_macos(config)
    else:
        print(f'对于当前系统你可能需要手动进行配置{config.system}')
        sys.exit(3)
    print('配置完成，对于某些系统你需要手动将CronWeb配置成服务')


def gen_user_cert(
        path_key: typing.Optional[typing.Union[str, pathlib.Path]],
        path_cert: typing.Optional[typing.Union[str, pathlib.Path]],
        serial: typing.Optional[str],
        config: InfoConfig,
        for_nginx: bool = False
):
    if not serial and not for_nginx:
        print('你需要用-s指定一个客户端证书序号')
        sys.exit(3)
    if for_nginx:
        print('生成nginx专用的客户端证书')
        if serial:
            print('为nginx生成的客户端证书不需要指定证书序列 直接为999')
        serial = '999'
    path_key = pathlib.Path(path_key) if path_key else config.ssl_ca_keyfile
    path_cert = pathlib.Path(path_cert) if path_cert else config.ssl_ca_certs
    if not path_key.exists() or not path_cert.exists():
        raise FileNotFoundError('客户端CA证书私钥或公钥不存在')

    if not check_openssl(config):
        print('似乎没有安装openssl，你可能需要手动生成客户端证书')
        return None

    if not for_nginx:
        path_user_cert = config.dir_client_cert_gen / f'client_{serial}.pem'
        path_user_key = config.dir_client_cert_gen / f'client_{serial}.key'
        path_user_csr = config.dir_client_cert_gen / f'client_{serial}.csr'
        path_user_pfx = config.dir_client_cert_gen / f'client_{serial}.pfx'
    else:
        path_user_cert = config.ssl_ca_certs.parent / f'client_nginx.pem'
        path_user_key = config.ssl_ca_certs.parent / f'client_nginx.key'
        path_user_csr = config.ssl_ca_certs.parent / f'client_nginx.csr'
        path_user_pfx = config.ssl_ca_certs.parent / f'client_nginx.pfx'

    if not path_user_cert.parent.exists():
        path_user_cert.parent.mkdir(parents=True)

    print('生成客户端证书私钥')
    subprocess.check_call([
        'openssl', 'genrsa', '-out', str(path_user_key), '2048'
    ])

    print('生成客户端证书公钥')
    subprocess.check_call([
        'openssl', 'req', '-new', '-key', str(path_user_key),
        '-out', str(path_user_csr), '-subj', f'/CN=CronWebClient_{serial}',
        '-addext', 'basicConstraints=CA:FALSE',
        '-addext', 'extendedKeyUsage=1.3.6.1.5.5.7.3.2',
        '-addext', 'keyUsage=digitalSignature'
    ])
    subprocess.check_call([
        'openssl', 'x509', '-req', '-days', '365',
        '-in', str(path_user_csr), '-out', str(path_user_cert),
        '-CAkey', str(path_key), '-CA', str(path_cert), '-set_serial', serial
    ])

    print('生成pfx证书')
    input_default('输入pfx证书密码', config.password_pfx, str, config, target='password_pfx')
    subprocess.check_call([
        'openssl', 'pkcs12', '-export',
        '-out', str(path_user_pfx), '-inkey', str(path_user_key),
        '-in', str(path_user_cert), '-certfile', str(path_cert),
        '-password', f'pass:{config.password_pfx}'
    ])

    print('客户端证书生成完成，请保护好生成的客户端证书')


def list_config_env(config: InfoConfig):
    print('[*] 在环境变量中配置过的值')
    for key in config.__dict__.keys():
        env_name = get_env_name(key)
        env_value = os.environ.get(env_name)
        value = f'{"* " + env_value if env_value else "  " + str(getattr(config, key))}'
        print(f'{env_name:-<35s} {value}')


if __name__ == '__main__':
    info_config = InfoConfig()

    parser = argparse.ArgumentParser(description='CronWeb安装工具')
    parser.add_argument('command', nargs='?', type=str,
                        help='gen-user: 生成服务证书 list-config-env: 列出可配置环境变量',
                        choices=['gen-user', 'list-config-env']
                        )
    parser.add_argument('--config-from-env', action='store_true', help='从环境变量中读取配置(而不是prompt询问)')
    parser.add_argument('--docker-mode', action='store_true', help='所有的yes or no自动选择默认选项(用于docker)')
    parser.add_argument('-s', '--serial', nargs='?', type=str, default=None,
                        help='指定生成的客户端证书序号')
    parser.add_argument('--for-nginx', action='store_true', help='生成nginx的客户端证书')
    parser.add_argument('-k', '--ca-key', nargs='?', type=str,
                        default=None,
                        help='客户端CA证书公钥路径(默认为certs/client_ca.pem)')
    parser.add_argument('-c', '--ca-cert', nargs='?', type=str,
                        default=None,
                        help='客户端CA证书私钥路径(默认为cert/client_ca.key)')
    args = parser.parse_args()

    if args.config_from_env is True:
        set_config_from_env(info_config)
    if args.docker_mode is True:
        info_config.docker_mode = True

    if args.command is None:
        route(info_config)
    elif args.command == 'gen-user':
        gen_user_cert(args.ca_key, args.ca_cert, args.serial, info_config, args.for_nginx)
    elif args.command == 'list-config-env':
        list_config_env(info_config)
