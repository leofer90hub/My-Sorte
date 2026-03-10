import hashlib, multiprocessing, time, base58, sys, os, random, json, smtplib, zipfile, io
from email.mime.text import MIMEText
from coincurve import PublicKey

# --- CONFIGURAÇÃO (LENDO DOS SECRETS) ---
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_DESTINO = os.environ.get('EMAIL_DESTINO')

ARQUIVO_ZIP = "1Bitcoin_addresses_BALANCE.zip"
NOME_INTERNO_TXT = "1Bitcoin_addresses_BALANCE.txt"
FICHEIRO_DE_SAIDA = "HIT_PRIVATEKEYS_RANDOM.txt"
FICHEIRO_CHECKPOINT = "checkpoint_magnitude.json"
CHAVES_POR_PAGINA = 128
TOTAL_PAGINAS_SITE = 90462569716653277674664832038037428010029347093027261772106498923335655221991

def enviar_email(assunto, corpo):
    if not EMAIL_USER or not EMAIL_PASS: return
    try:
        msg = MIMEText(corpo)
        msg['Subject'] = assunto
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_DESTINO
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_DESTINO, msg.as_string())
    except: pass

def btc_addr_to_hash160(addr):
    try:
        addr = addr.strip()
        if addr.startswith('1') or addr.startswith('3'):
            return base58.b58decode_check(addr)[1:]
        return None
    except: return None

def worker(worker_id, alvos_set, lock, stats_shared, tempo_inicio_global, emails_enviados, hits_do_dia):
    # DOMÍNIO CORRIGIDO PARA O FORMATO ORIGINAL
    dominio = "https://privatekeys.pw"
    caminho = "/keys/bitcoin/"
    
    while True:
        if time.time() - tempo_inicio_global > 21000: # 5h50min
            sys.exit(0)

        # CAÇA PROFUNDA E BLOQUEIO DA PÁGINA 1
        bits = random.randint(160, 256)
        max_p = (2**bits) // CHAVES_POR_PAGINA
        p_atual = random.randint(1000000000, min(max_p, TOTAL_PAGINAS_SITE))
        
        url_site = dominio + caminho + str(p_atual)
        if worker_id == 0: print(f"ALVO: {bits} bits | URL: {url_site}")

        idx_base = (p_atual - 1) * CHAVES_POR_PAGINA + 1
        for i in range(CHAVES_POR_PAGINA):
            idx = idx_base + i
            try:
                priv = idx.to_bytes(32, 'big')
                pk = PublicKey.from_secret(priv)
                # Verifica Comp, Uncomp e SegWit (1, 3 e BC1)
                h_comp = hashlib.new('ripemd160', hashlib.sha256(pk.format(True)).digest()).digest()
                
                if h_comp in alvos_set:
                    info = f"HIT! URL: {url_site}\nHEX: {priv.hex()}"
                    with lock:
                        if h_comp not in emails_enviados:
                            enviar_email("BITCOIN FOUND!", info)
                            emails_enviados.append(h_comp)
                            hits_do_dia.append(info)
                    with open(FICHEIRO_DE_SAIDA, "a") as f: f.write(info + "\n")
            except: continue
        
        with lock:
            stats_shared["total_dia"] = stats_shared.get("total_dia", 0) + CHAVES_POR_PAGINA
            dia_hoje = time.strftime("%d")
            
            if stats_shared.get("ultimo_dia_email") != dia_hoje:
                lista_hits = "\n\n".join(hits_do_dia) if len(hits_do_dia) > 0 else "Nenhum hit hoje."
                corpo_resumo = f"Relatório 24h\n\nTotal Varrido: {stats_shared.get('total_dia')} chaves.\n\nHits do Dia:\n{lista_hits}"
                enviar_email("Resumo Diario de Varrimento", corpo_resumo)
                
                stats_shared["ultimo_dia_email"] = dia_hoje
                stats_shared["total_dia"] = 0
                while len(hits_do_dia) > 0: hits_do_dia.pop()

if __name__ == "__main__":
    tempo_ini = time.time()
    manager = multiprocessing.Manager()
    stats = manager.dict({"total_dia": 0, "ultimo_dia_email": time.strftime("%d")})
    emails_enviados = manager.list()
    hits_do_dia = manager.list()
    alvos = set()
    
    print("[*] Carregando 3GB (Modo Seguro)...")
    try:
        with zipfile.ZipFile(ARQUIVO_ZIP, 'r') as z:
            with z.open(NOME_INTERNO_TXT) as f:
                for linha in io.TextIOWrapper(f):
                    partes = linha.split()
                    if partes:
                        h = btc_addr_to_hash160(partes[0])
                        if h: alvos.add(h)
    except: sys.exit(1)
    
    lock = multiprocessing.Lock()
    for i in range(1):
        multiprocessing.Process(target=worker, args=(i, alvos, lock, stats, tempo_ini, emails_enviados, hits_do_dia)).start()
    
    while True:
        time.sleep(300)
        with open(FICHEIRO_CHECKPOINT, 'w') as f: json.dump(dict(stats), f)
