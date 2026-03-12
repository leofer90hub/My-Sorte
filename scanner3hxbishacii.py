import os, hashlib, random, time, smtplib, zipfile, mmap, binascii, sys
from datetime import datetime
from email.mime.text import MIMEText
from bit import Key # Requer: pip install bit

# --- CONFIGURAÇÃO GITHUB SECRETS ---
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_DEST = os.getenv("EMAIL_DESTINO")
ZIP_NAME = "1Bitcoin_addresses_BALANCE.zip"
TXT_NAME = "1Bitcoin_addresses_BALANCE.txt"

stats = {"count": 0, "last_report": ""}

def enviar_alerta(tipo, pk, addr):
    corpo = f"ALERTA HIT!\nTipo: {tipo}\nPrivKey: {pk}\nAddr: {addr}\nData: {datetime.now()}"
    msg = MIMEText(corpo); msg['Subject'] = f"BITCOIN FOUND: {tipo}!"; msg['From'] = EMAIL_USER; msg['To'] = EMAIL_DEST
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_USER, EMAIL_PASS)
            s.sendmail(EMAIL_USER, EMAIL_DEST, msg.as_string())
    except: pass

def busca_binaria(m, addr):
    """Busca O(log n) no ficheiro mapeado - Essencial para 7GB RAM"""
    low, high = 0, m.size()
    addr_bytes = addr.encode()
    while low < high:
        mid = (low + high) // 2
        m.seek(mid)
        m.readline() # Sincroniza com o início da linha seguinte
        line = m.readline().strip()
        if not line: break
        if line == addr_bytes: return True
        if line < addr_bytes: low = m.tell()
        else: high = mid
    return False

def processar_salada_completa(seed_bytes):
    """A 'Salada Russa' sem cortes: Hex, SHA-Bin, SHA-ASCII, SHA-Bits, Endian"""
    h = seed_bytes.hex().zfill(64)
    b_str = bin(int(h, 16))[2:].zfill(256)
    
    return [
        h,                                           # 1. Hex Puro
        hashlib.sha256(seed_bytes).hexdigest(),      # 2. SHA256 do Binário
        hashlib.sha256(h.encode()).hexdigest(),      # 3. SHA256 do Texto Hex (ASCII)
        hashlib.sha256(b_str.encode()).hexdigest(),  # 4. SHA256 da string "0101..."
        seed_bytes[::-1].hex().zfill(64)             # 5. Endianness Invertido
    ]

def run():
    print("[*] Extraindo base de dados..."); sys.stdout.flush()
    with zipfile.ZipFile(ZIP_NAME, 'r') as z:
        z.extract(TXT_NAME)

    # Ordenação automática para garantir que a Busca Binária funcione
    print("[*] Verificando ordenação (Plug & Play)..."); sys.stdout.flush()
    os.system(f"sort -u {TXT_NAME} -o {TXT_NAME}")

    with open(TXT_NAME, "rb") as f:
        # Mapeia o ficheiro de 3GB para busca instantânea usando 0 RAM
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        print("[*] Sniper Salada Russa ATIVO. Varrimento 1-256 bits iniciado."); sys.stdout.flush()

        while True:
            # ENTROPIA VARIÁVEL: De 1 a 256 bits (aleatório ao calhas)
            bits = random.randint(1, 256)
            seed = os.urandom((bits + 7) // 8)
            
            candidatos = processar_salada_completa(seed)
            
            for pk in candidatos:
                stats["count"] += 1
                
                # MOSTRAR PROGRESSO (A cada 100k chaves varridas)
                if stats["count"] % 100000 == 0:
                    print(f"[*] Varridas: {stats['count']} | Estabilidade: OK | {datetime.now().strftime('%H:%M:%S')}")
                    sys.stdout.flush()

                try:
                    # Gerador Multiformato (bc1, 1, 3, Comp/Uncomp)
                    k = Key.from_hex(pk)
                    # Lista de alvos: Legacy, SegWit P2SH, Bech32 e Legacy Uncompressed
                    addrs = [k.address, k.segwit_address, k.address_uncompressed]
                    
                    for a in addrs:
                        if a and busca_binaria(m, a):
                            enviar_alerta("SALADA_RUSSA_COMPLETA", pk, a)
                except: continue

                        # Relatório diário às 00:10
            agora = datetime.now()
            if agora.hour == 0 and agora.minute == 10 and stats["last_report"] != agora.day:
                enviar_alerta("STATUS_DIARIO", f"Chaves varridas nesta sessao: {stats['count']}", "N/A")
                stats["last_report"] = agora.day
                stats["count"] = 0
                time.sleep(60)

if __name__ == "__main__":
    run()
