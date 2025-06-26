import subprocess
import re
import json
import time
import threading
import logging
from datetime import datetime
import redis

# Configuracao de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/opt/br10dashboard/logs/system_monitor.log',
    filemode='a'
)
logger = logging.getLogger('system_monitor')

# Adicionar log no terminal
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class SystemMonitor:
    def __init__(self):
        self.cpu_stats = []
        self.memory_stats = []
        self.io_stats = []
        self.top_processes = []
        self.io_processes = []
        self.last_update = None
        self.monitor_thread = None
        self.running = False
        self._lock = threading.Lock()
        self.last_redis_update = 0
        self.redis_interval = 300  # 5 minutos em segundos
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
        logger.info("SystemMonitor inicializado")
        
    def start_monitoring(self, interval=60):
        """Inicia o monitoramento em background com intervalo de 1 minuto"""
        if self.running:
            logger.info("Monitoramento ja esta em execucao")
            return False
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info(f"Monitoramento de recursos iniciado com intervalo de {interval} segundos")
        print(f"[INFO] Monitoramento iniciado com intervalo de {interval}s")
        return True
        
    def stop_monitoring(self):
        """Para o monitoramento em background"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            self.monitor_thread = None
        logger.info("Monitoramento de recursos parado")
        print("[INFO] Monitoramento parado")
        
    def _monitor_loop(self, interval):
        """Loop de monitoramento em background"""
        logger.info(f"Loop de monitoramento iniciado com intervalo de {interval}s")
        while self.running:
            try:
                success = self.update_stats()
                self._update_redis_stats()  # Atualiza Redis periodicamente
                logger.info(f"Atualizacao de estatisticas: {'sucesso' if success else 'falha'}")
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento: {e}")
                print(f"[ERRO] Falha no loop de monitoramento: {e}")
                time.sleep(interval)
                
    def _update_redis_stats(self):
        """Atualiza estatísticas no Redis periodicamente (a cada 5 minutos)"""
        try:
            current_time = time.time()
            if current_time - self.last_redis_update >= self.redis_interval:
                stats = self.get_stats()
                self.redis_client.set('system_stats', json.dumps(stats))
                self.redis_client.expire('system_stats', self.redis_interval * 2)
                self.last_redis_update = current_time
                logger.info("Estatísticas atualizadas no Redis")
        except Exception as e:
            logger.error(f"Erro ao atualizar Redis: {e}")
                
    def update_stats(self):
        """Atualiza todas as estatisticas do sistema"""
        with self._lock:
            try:
                # Coletar estatisticas
                print("[INFO] Atualizando estatisticas do sistema...")
                self._update_cpu_memory_stats()
                self._update_io_stats()
                self._update_top_processes()
                self._update_io_processes()
                
                # Atualizar timestamp
                self.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[INFO] Estatisticas atualizadas em {self.last_update}")
                return True
            except Exception as e:
                logger.error(f"Erro ao atualizar estatisticas do sistema: {e}")
                print(f"[ERRO] Falha ao atualizar estatisticas: {e}")
                return False

    def _update_cpu_memory_stats(self):
        """Atualiza estatisticas de CPU e memoria usando o comando top"""
        print("[INFO] Atualizando estatisticas de CPU e memoria...")
        try:
            cmd = "top -b -n 1"
            print(f"[DEBUG] Executando comando: {cmd}")
            output = subprocess.check_output(cmd, universal_newlines=True, shell=True)
            
            # Extrair estatisticas de CPU
            cpu_pattern = r'%CPU\(s\):\s+(\d+,\d+)\s+us,\s+(\d+,\d+)\s+sy,\s+(\d+,\d+)\s+ni,\s+(\d+,\d+)\s+id'
            cpu_match = re.search(cpu_pattern, output)
            
            cpu_stats = {
                "user": 0,
                "system": 0,
                "nice": 0,
                "idle": 100,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            
            if cpu_match:
                cpu_stats["user"] = float(cpu_match.group(1).replace(',', '.'))
                cpu_stats["system"] = float(cpu_match.group(2).replace(',', '.'))
                cpu_stats["nice"] = float(cpu_match.group(3).replace(',', '.'))
                cpu_stats["idle"] = float(cpu_match.group(4).replace(',', '.'))
                print(f"[DEBUG] CPU: user={cpu_stats['user']}%, system={cpu_stats['system']}%, idle={cpu_stats['idle']}%")
            else:
                print("[AVISO] Padrao de CPU nao encontrado na saida do top")
                logger.warning("Padrao de CPU nao encontrado na saida do top")
            
            # Extrair estatisticas de memoria
            mem_pattern = r'MB mem :\s+(\d+,\d+)\s+total,\s+(\d+,\d+)\s+free,\s+(\d+,\d+)\s+used,\s+(\d+,\d+)\s+buff/cache'
            mem_match = re.search(mem_pattern, output)
        
            mem_stats = {
                "total": 0,
                "free": 0,
                "used": 0,
                "cached": 0,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            
            if mem_match:
                mem_stats["total"] = float(mem_match.group(1).replace(',', '.'))
                mem_stats["free"] = float(mem_match.group(2).replace(',', '.'))
                mem_stats["used"] = float(mem_match.group(3).replace(',', '.'))
                mem_stats["cached"] = float(mem_match.group(4).replace(',', '.'))
                print(f"[DEBUG] Memoria: total={mem_stats['total']}MB, used={mem_stats['used']}MB, free={mem_stats['free']}MB")
            else:
                # Tentar formato alternativo
                mem_pattern = r'KiB Mem :\s+(\d+)\s+total,\s+(\d+)\s+free,\s+(\d+)\s+used,\s+(\d+)\s+buff/cache'
                mem_match = re.search(mem_pattern, output)
                if mem_match:
                    mem_stats["total"] = float(mem_match.group(1)) / 1024
                    mem_stats["free"] = float(mem_match.group(2)) / 1024
                    mem_stats["used"] = float(mem_match.group(3)) / 1024
                    mem_stats["cached"] = float(mem_match.group(4)) / 1024
                    print(f"[DEBUG] Memoria (KiB): total={mem_stats['total']}MB, used={mem_stats['used']}MB, free={mem_stats['free']}MB")
                else:
                    print("[AVISO] Padrao de memoria nao encontrado na saida do top")
                    logger.warning("Padrao de memoria nao encontrado na saida do top")
            
            # Adicionar as listas de historico
            self.cpu_stats.append(cpu_stats)
            self.memory_stats.append(mem_stats)
            
            # Limitar o tamanho do historico
            if len(self.cpu_stats) > 60:
                self.cpu_stats = self.cpu_stats[-60:]
            if len(self.memory_stats) > 60:
                self.memory_stats = self.memory_stats[-60:]
            
            print("[INFO] Estatisticas de CPU e memoria atualizadas com sucesso")
                
        except Exception as e:
            logger.error(f"Erro ao atualizar estatisticas de CPU/Memoria: {e}")
            print(f"[ERRO] Falha ao atualizar CPU/Memoria: {e}")
            
    def _update_io_stats(self):
        """Atualiza estatisticas de I/O usando o comando iostat"""
        print("[INFO] Atualizando estatisticas de I/O...")
        try:
            cmd = "iostat -d -x 1 1"
            print(f"[DEBUG] Executando comando: {cmd}")
            output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.PIPE, shell=True)
            
            # Extrair dados de I/O por dispositivo
            disk_stats = []
            
            lines = output.splitlines()
            device_header_idx = -1
            
            # Encontrar o indice do cabecalho do dispositivo
            for i, line in enumerate(lines):
                if "Device" in line and "r/s" in line and "w/s" in line:
                    device_header_idx = i
                    break
            
            if device_header_idx > 0 and device_header_idx < len(lines) - 1:
                for line in lines[device_header_idx + 1:]:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 6:
                            device = parts[0]
                            
                            # Ignorar dispositivos loop
                            if device.startswith("loop"):
                                continue
                             
                            read_per_sec = float(parts[1].replace(',', '.'))
                            write_per_sec = float(parts[2].replace(',', '.'))
                            
                            # Obter indices para outras metricas
                            util_idx = -1
                            for idx, header in enumerate(lines[device_header_idx].split()):
                                if header == "%util":
                                    util_idx = idx
                                    break
                            
                            utilization = float(parts[util_idx].replace(',', '.')) if util_idx >= 0 and util_idx < len(parts) else 0
                            
                            disk_stats.append({
                                "device": device,
                                "read_per_sec": read_per_sec,
                                "write_per_sec": write_per_sec,
                                "utilization": utilization
                            })
                            print(f"[DEBUG] Disco {device}: read={read_per_sec}r/s, write={write_per_sec}w/s, util={utilization}%")
            
            # Adicionar ao historico
            if disk_stats:
                io_stat = {
                    "disks": disk_stats,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                self.io_stats.append(io_stat)
                
                # Limitar o tamanho do historico
                if len(self.io_stats) > 60:
                    self.io_stats = self.io_stats[-60:]
                
                print(f"[INFO] Estatisticas de I/O atualizadas: {len(disk_stats)} dispositivos")
            else:
                print("[AVISO] Nenhum dispositivo de disco encontrado")
                
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.warning(f"Nao foi possivel executar iostat. Tentando metodo alternativo: {e}")
            print(f"[AVISO] Erro ao executar iostat: {e}")
            
            try:
                # Metodo alternativo usando /proc/diskstats
                with open('/proc/diskstats', 'r') as file:
                    disk_stats = []
                    print("[DEBUG] Lendo /proc/diskstats como alternativa")
                    
                    for line in file:
                        parts = line.split()
                        if len(parts) >= 14:
                            # Pular dispositivos loop e ram
                            if parts[2].startswith(('loop', 'ram')):
                                continue
                                
                            device = parts[2]
                            read_ios = int(parts[3])
                            write_ios = int(parts[7])
                            
                            disk_stats.append({
                                "device": device,
                                "read_per_sec": 0,  # Nao temos taxa, apenas total
                                "write_per_sec": 0,
                                "reads_total": read_ios,
                                "writes_total": write_ios,
                                "utilization": 0
                            })
                            print(f"[DEBUG] Disco {device}: reads={read_ios}, writes={write_ios}")
                    
                    if disk_stats:
                        io_stat = {
                            "disks": disk_stats,
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        }
                        
                        self.io_stats.append(io_stat)
                        
                        # Limitar o tamanho do historico
                        if len(self.io_stats) > 60:
                            self.io_stats = self.io_stats[-60:]
                        
                        print(f"[INFO] Estatisticas de I/O alternativas atualizadas: {len(disk_stats)} dispositivos")
            except Exception as e:
                logger.error(f"Erro ao ler /proc/diskstats: {e}")
                print(f"[ERRO] Falha ao ler /proc/diskstats: {e}")
        except Exception as e:
            logger.error(f"Erro ao atualizar estatisticas de I/O: {e}")
            print(f"[ERRO] Falha ao atualizar estatisticas de I/O: {e}")
            
    def _update_top_processes(self):
        """Atualiza a lista de processos que consomem mais CPU/memoria"""
        print("[INFO] Atualizando lista de processos...")
        try:
            cmd = "ps -eo pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,comm --sort=-%cpu,%mem --no-headers"
            print(f"[DEBUG] Executando comando: {cmd}")
            output = subprocess.check_output(cmd, universal_newlines=True, shell=True)
            
            top_processes = []
            
            for i, line in enumerate(output.splitlines()):
                if i >= 15:  # Limitar a 15 processos
                    break
                    
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    proc = {
                        "pid": parts[0],
                        "ppid": parts[1],
                        "user": parts[2],
                        "cpu_percent": float(parts[3].replace(',', '.')),
                        "mem_percent": float(parts[4].replace(',', '.')),
                        "vsz": int(parts[5]),
                        "rss": int(parts[6]),
                        "stat": parts[7],
                        "start_time": parts[8],
                        "time": parts[9],
                        "command": parts[10]
                    }
                    top_processes.append(proc)
                    if i < 5:  # Exibir apenas os 5 primeiros no log
                        print(f"[DEBUG] Processo {proc['pid']}: CPU={proc['cpu_percent']}%, MEM={proc['mem_percent']}%, CMD={proc['command']}")
            
            self.top_processes = top_processes
            print(f"[INFO] Lista de processos atualizada: {len(top_processes)} processos")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar lista de processos: {e}")
            print(f"[ERRO] Falha ao atualizar lista de processos: {e}")
            
    def _update_io_processes(self):
        """Atualiza a lista de processos que consomem mais I/O usando iotop"""
        print("[INFO] Atualizando processos de I/O...")
        try:
            # Verificar se o iotop esta instalado
            check_cmd = "which iotop"
            print(f"[DEBUG] Verificando iotop: {check_cmd}")
            check_iotop = subprocess.run(check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            
            if check_iotop.returncode != 0:
                logger.warning("iotop nao esta instalado. Nao sera possivel coletar estatisticas de I/O por processo.")
                print("[AVISO] iotop nao esta instalado. Ignorando coleta de estatisticas de I/O por processo.")
                return
            
            # Executar iotop uma vez no modo batch
            cmd = "iotop -b -n 1 -o"
            print(f"[DEBUG] Executando comando: {cmd}")
            output = subprocess.check_output(cmd, universal_newlines=True, shell=True)
            
            io_processes = []
            process_started = False
            
            for line in output.splitlines():
                if "Total DISK READ" in line:
                    # Extrair totais de leitura/escrita
                    try:
                        disk_read_match = re.search(r'Total DISK READ:\s+([0-9.]+\s+[A-Za-z]/s)', line)
                        disk_write_match = re.search(r'Total DISK WRITE:\s+([0-9.]+\s+[A-Za-z]/s)', line)
                        
                        total_read = disk_read_match.group(1) if disk_read_match else "0 B/s"
                        total_write = disk_write_match.group(1) if disk_write_match else "0 B/s"
                        
                        io_processes.append({
                            "total_read": total_read,
                            "total_write": total_write,
                            "processes": []
                        })
                        print(f"[DEBUG] I/O Total: read={total_read}, write={total_write}")
                    except Exception as e:
                        logger.error(f"Erro ao processar linha de totais de I/O: {e}")
                        print(f"[ERRO] Falha ao processar totais de I/O: {e}")
                        
                elif "TID" in line and "PRIO" in line:
                    process_started = True
                    continue
                
                if process_started and io_processes and line.strip():
                    try:
                        # Verificar se a linha tem o formato esperado
                        parts = line.split(None, 9)
                        
                        if len(parts) >= 10:
                            pid = parts[0]
                            prio = parts[1]
                            user = parts[2]
                            disk_read = parts[3]
                            disk_write = parts[4]
                            command = parts[9]
                            
                            # Adicionar apenas se ha alguma atividade de I/O
                            if disk_read != "0.00 B/s" or disk_write != "0.00 B/s":
                                io_processes[0]["processes"].append({
                                    "pid": pid,
                                    "prio": prio,
                                    "user": user,
                                    "disk_read": disk_read,
                                    "disk_write": disk_write,
                                    "command": command
                                })
                                print(f"[DEBUG] I/O Processo {pid}: read={disk_read}, write={disk_write}, cmd={command}")
                    except Exception as e:
                        logger.error(f"Erro ao processar linha de processo I/O: {e}")
                        print(f"[ERRO] Falha ao processar processo I/O: {e}")
            
            # Limitar a 10 processos
            if io_processes and "processes" in io_processes[0]:
                io_processes[0]["processes"] = io_processes[0]["processes"][:10]
                print(f"[INFO] Processos I/O atualizados: {len(io_processes[0]['processes'])} processos")
            
            self.io_processes = io_processes
            
        except Exception as e:
            logger.error(f"Erro ao atualizar lista de processos de I/O: {e}")
            print(f"[ERRO] Falha ao atualizar processos I/O: {e}")
            
    def get_stats(self, from_redis=False):
        """Retorna todas as estatisticas atuais como um dicionario"""
        if from_redis:
            try:
                cached_stats = self.redis_client.get('system_stats')
                if cached_stats:
                    return json.loads(cached_stats)
            except Exception as e:
                logger.error(f"Erro ao obter do Redis: {e}")
        
        with self._lock:
            stats = {
                "cpu": self.cpu_stats[-1] if self.cpu_stats else {},
                "memory": self.memory_stats[-1] if self.memory_stats else {},
                "io": self.io_stats[-1] if self.io_stats else {},
                "top_processes": self.top_processes,
                "io_processes": self.io_processes,
                "history": {
                    "cpu": self.cpu_stats,
                    "memory": self.memory_stats,
                    "io": self.io_stats
                },
                "last_update": self.last_update
            }
            print(f"[INFO] Estatisticas obtidas: CPU={len(self.cpu_stats)}, Memory={len(self.memory_stats)}, IO={len(self.io_stats)}, Processos={len(self.top_processes)}")
            return stats

# Instancia global do monitor de sistema
print("[INFO] Inicializando monitor de sistema...")
system_monitor = SystemMonitor()

# Funcoes para gerenciar o monitor
def start_system_monitor(interval=60):
    print(f"[INFO] Iniciando monitoramento com intervalo={interval}s")
    return system_monitor.start_monitoring(interval)

def stop_system_monitor():
    print("[INFO] Parando monitoramento")
    return system_monitor.stop_monitoring()

def get_system_stats(update=False, from_redis=True):
    if update:
        print("[INFO] Atualizando e obtendo estatisticas")
        system_monitor.update_stats()
    else:
        print("[INFO] Obtendo estatisticas atuais")
    return system_monitor.get_stats(from_redis=from_redis)

# Teste para verificar se o modulo foi carregado corretamente
print("[INFO] Modulo system_resources carregado com sucesso!")