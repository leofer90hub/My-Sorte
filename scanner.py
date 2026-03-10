import hashlib, multiprocessing, time, base58, sys, os, random, json, smtplib, zipfile, io
from email.mime.text import MIMEText
from coincurve import PublicKey

# --- CONFIGURAÇÃO DE FICHEIROS ---
ARQUIVO_ZIP = "1Bitcoin_addresses_BALANCE.zip"
NOME_INTERNO_TXT = "1Bitcoin_addresses_BALANCE.txt"
FICHEIRO_DE_SAIDA = "HIT_PRIVATEKEYS_RANDOM.txt"
FICHEIRO_CHECKPOINT = "checkpoint_magnitude.json"
CHAVES_POR_PAGINA = 128
TOTAL_PAGINAS_SITE = 2573157538607026564968244111304175730063056983979442319613448069811514699875

# --- CONFIGURAÇÃO ZUMBI + EMAIL ---
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_DESTINO = os.environ.get('EMAIL_DESTINO')
LIMITE_TEMPO_SEGUNDOS = 21000      # 5 Horas e 50 Minutos

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

def bech32_decode_address(addr):
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    try:
        if not addr.startswith("bc1q"): return None
        data = addr[4:-6]
        res = [CHARSET.find(char) for char in data]
        acc, val, bits = 0, 0, 0
        ret = []
        for v in res:
            val = (val << 5) | v
            bits += 5
            while bits >= 8:
                bits -= 8
                ret.append((val >> bits) & 0xff)
        return bytes(ret)
    except: return None

def btc_addr_to_hash160(addr):
    addr = addr.strip()
    try:
        if addr.startswith('1') or addr.startswith('3'):
            return base58.b58decode_check(addr)[1:]
        if addr.startswith('bc1q'):
            return bech32_decode_address(addr)
        return None
    except: return None

def carregar_progresso():
    if os.path.exists(FICHEIRO_CHECKPOINT):
        try:
            with open(FICHEIRO_CHECKPOINT, 'r') as f:
                data = json.load(f)
                if "ultimo_dia" not in data: data["ultimo_dia"] = time.strftime("%d")
                if "total_dia" not in data: data["total_dia"] = 0
                return data
        except: pass
    return {"ultimo_dia": time.strftime("%d"), "total_dia": 0}

def salvar_progresso(stats_dict):
    with open(FICHEIRO_CHECKPOINT, 'w') as f:
        json.dump(dict(stats_dict), f)

def worker(worker_id, alvos_set, lock, contador_global, stats_shared, tempo_inicio_global, emails_enviados):
    dominio = "https://privatekeys.pw"
    caminho = "/keys/bitcoin/"
    
    while True:
        if time.time() - tempo_inicio_global > LIMITE_TEMPO_SEGUNDOS:
            if worker_id == 0: salvar_progresso(stats_shared)
            sys.exit(0)

        # --- NOVA LÓGICA: EVITAR PÁGINA 1 E MAGNITUDES BAIXAS ---
        # 95% das vezes foca em chaves reais (160-256 bits). 5% explora o resto acima de 40 bits.
        if random.random() > 0.05:
            bits_escolhidos = random.randint(160, 256)
        else:
            bits_escolhidos = random.randint(40, 159)

        with lock:
            stats_shared[str(bits_escolhidos)] = stats_shared.get(str(bits_escolhidos), 0) + 1

        max_pags = (2**bits_escolhidos) // CHAVES_POR_PAGINA
        if max_pags > TOTAL_PAGINAS_SITE: max_pags = TOTAL_PAGINAS_SITE
        
        # Garante que nunca cai nas primeiras 1000 páginas se a magnitude permitir
        p_min = 1000 if max_pags > 1000 else 1
        pagina_atual = random.randint(p_min, max_pags) if max_pags > p_min else p_min
        
        url_site = dominio + caminho + str(pagina_atual)
        if worker_id == 0: print(f"ALVO: {bits_escolhidos} bits | URL: {url_site}")

        indice_base = (pagina_atual - 1) * CHAVES_POR_PAGINA + 1
        for i in range(CHAVES_POR_PAGINA):
            idx = indice_base + i
            try:
                priv_bytes = idx.to_bytes(32, 'big')
                pk_obj = PublicKey.from_secret(priv_bytes)
                h_comp = hashlib.new('ripemd160', hashlib.sha256(pk_obj.format(True)).digest()).digest()
                h_uncomp = hashlib.new('ripemd160', hashlib.sha256(pk_obj.format(False)).digest()).digest()
                h_seg = hashlib.new('ripemd160', hashlib.sha256(b'\x00\x14' + h_comp).digest()).digest()

                for h_bin, tipo in [(h_comp, "Comp"), (h_uncomp, "Uncomp"), (h_seg, "SegWit")]:
                    if h_bin in alvos_set:
                        info = f"HIT {tipo}! URL: {url_site}\nHEX: {priv_bytes.hex()}"
                        with lock:
                            if h_bin not in emails_enviados:
                                enviar_email("BITCOIN FOUND!", info)
                                emails_enviados.append(h_bin)
                        with open(FICHEIRO_DE_SAIDA, "a") as f: f.write(info + "\n")
            except: continue
        
        with lock:
            stats_shared["total_dia"] = stats_shared.get("total_dia", 0) + CHAVES_POR_PAGINA
            if stats_shared.get("ultimo_dia") != time.strftime("%d"):
                enviar_email("Resumo Diario", f"Varremos hoje: {stats_shared['total_dia']} chaves.")
                stats_shared["total_dia"], stats_shared["ultimo_dia"] = 0, time.strftime("%d")
                salvar_progresso(stats_shared)

if __name__ == "__main__":
    tempo_inicio_global = time.time()
    manager = multiprocessing.Manager()
    stats_shared = manager.dict(carregar_progresso())
    emails_enviados = manager.list()
    alvos_bin = set()

    print("[*] Lendo ZIP para RAM (Modo Economia)...")
    try:
        with zipfile.ZipFile(ARQUIVO_ZIP, 'r') as z:
            with z.open(NOME_INTERNO_TXT) as f:
                wrapper = io.TextIOWrapper(f)
                for linha in wrapper:
                    partes = linha.split()
                    if partes:
                        h = btc_addr_to_hash160(partes[0])
                        if h: alvos_bin.add(h)
                del wrapper
    except Exception as e: sys.exit(1)

    lock = multiprocessing.Lock()
    contador = multiprocessing.Value('q', 0)
    # APENAS 1 PROCESSO para evitar congelamento da RAM
    for i in range(1):
        p = multiprocessing.Process(target=worker, args=(i, alvos_bin, lock, contador, stats_shared, tempo_inicio_global, emails_enviados))
        p.start()
    
    while True: time.sleep(60) # Verifica a cada minuto
