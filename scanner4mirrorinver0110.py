import os, hashlib, random, time, smtplib, zipfile, binascii, sys
from datetime import datetime
from email.mime.text import MIMEText
from bit import Key # Requer: pip install bit

# --- CONFIGURAÇÃO ---
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_DEST = os.getenv("EMAIL_DESTINO")
ZIP_NAME = "1Bitcoin_addresses_BALANCE.zip"
TXT_NAME = "1Bitcoin_addresses_BALANCE.txt"

stats = {"count": 0, "last_report": ""}

def enviar_alerta(assunto, corpo):
    if not EMAIL_USER: return
    msg = MIMEText(corpo); msg['Subject'] = assunto; msg['From'] = EMAIL_USER; msg['To'] = EMAIL_DEST
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_USER, EMAIL_PASS); s.sendmail(EMAIL_USER, EMAIL_DEST, msg.as_string())
    except: pass

def mutacao_total(bits_str):
    """Gera Salada Mutante: Espelhamento Binário, Decimal e Hex"""
    candidatos = []
    
    # 1. Binário Original -> Hex
    val_dec = int(bits_str, 2)
    h_orig = hex(val_dec)[2:].zfill(64)
    candidatos.append(h_orig)
    
    # 2. Espelhamento Binário (Mirror bits: 1011 -> 1101)
    h_bin_mirror = hex(int(bits_str[::-1], 2))[2:].zfill(64)
    candidatos.append(h_bin_mirror)
    
    # 3. Inversão Decimal (Mirror decimal: 123 -> 321)
    dec_str_rev = str(val_dec)[::-1]
    h_dec_rev = hashlib.sha256(dec_str_rev.encode()).hexdigest()
    candidatos.append(h_dec_rev)
    
    # 4. Inversão de Bytes Hex (Endianness: AABB -> BBAA)
    try:
        seed_bytes = binascii.unhexlify(h_orig)
        candidatos.append(seed_bytes[::-1].hex().zfill(64))
    except: pass
    
    # 5. SHA256 do Decimal Puro (O contra-ataque padrão)
    candidatos.append(hashlib.sha256(str(val_dec).encode()).hexdigest())

    return list(set(candidatos))

def run():
    print("[*] Carregando 3GB de Balances (RAM Set)..."); sys.stdout.flush()
    try:
        with zipfile.ZipFile(ZIP_NAME, 'r') as z:
            with z.open(TXT_NAME) as f:
                # Carregar para SET para velocidade máxima na RAM
                balances = set(line.strip().decode() for line in f)
        print(f"[*] Sniper Mutante Ativo. {len(balances)} alvos carregados."); sys.stdout.flush()
    except Exception as e:
        print(f"Erro: {e}"); sys.stdout.flush(); return

    while True:
        # Gera semente binária aleatória (1-256 bits)
        size = random.randint(1, 256)
        bits = "".join(random.choice("01") for _ in range(size))
        
        for pk in mutacao_total(bits):
            stats["count"] += 1
            
            # MOSTRAR PROGRESSO (A cada 100k chaves)
            if stats["count"] % 100000 == 0:
                print(f"[*] Mutante Varridas: {stats['count']} | OK | {datetime.now().strftime('%H:%M:%S')}")
                sys.stdout.flush()

            try:
                k = Key.from_hex(pk)
                # Testa Legacy (1), SegWit P2SH (3), Bech32 (bc1) e Uncompressed
                # Nested SegWit (3) é gerado por k.to_nested_p2sh_address()
                addrs = [k.address, k.segwit_address, k.address_uncompressed, k.to_nested_p2sh_address()]
                
                for a in addrs:
                    if a in balances:
                        msg = f"!!! HIT MUTANTE !!!\nPrivKey: {pk}\nAddr: {a}\nBits: {len(bits)}"
                        enviar_alerta("BITCOIN FOUND - MUTANTE", msg)
                        with open("HITS_MUTANTE.txt", "a") as f: f.write(msg + "\n")
            except: continue

                # Relatório 00:15
        now = datetime.now()
        if now.hour == 0 and now.minute == 15 and stats["last_report"] != now.day:
            enviar_alerta("Relatorio Sniper Mutante", f"Varridas: {stats['count']}")
            stats["last_report"] = now.day; stats["count"] = 0; time.sleep(60)

if __name__ == "__main__":
    run()
