"""
Patuá Solar — Sistema Web Completo v4 (Supabase)
  /gestor → dashboard + upload + relatório
  /usina  → somente leitura
Deploy: uvicorn main:app --host 0.0.0.0 --port $PORT
"""
import re, json, os, io
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
import pdfplumber
from supabase import create_client, Client

app = FastAPI()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mrxvcczkshsdpzbmjzwh.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1yeHZjY3prc2hzZHB6Ym1qendoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI3MDUzNDIsImV4cCI6MjA5ODI4MTM0Mn0.MmON1h6yRnbk9alczXUmaTv4_0Y8CMXyTrMn9em89W0")
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CLIENTES_CONFIG = {
    "Real Evolution": {"cod":"2972408-2","cod_instalacao":"1071042","end":"SQNW 109",        "tarifa_neo":0.97030,"tarifa_mtec":0.77624,"desconto":0.20,"fim":"Jul/27","prog":68},
    "SQS 314":        {"cod":"3079816-7","cod_instalacao":"1815",   "end":"SQS 314",          "tarifa_neo":0.99926,"tarifa_mtec":0.81939,"desconto":0.18,"fim":"Ago/26","prog":90},
    "Oasis Design":   {"cod":"3079816",  "cod_instalacao":"1214090","end":"Águas Claras",     "tarifa_neo":0.95975,"tarifa_mtec":0.76780,"desconto":0.20,"fim":"Mar/27","prog":58},
    "Bello Trigo":    {"cod":"3140795",  "cod_instalacao":"1396714","end":"Jardim Botânico",  "tarifa_neo":0.98049,"tarifa_mtec":0.78439,"desconto":0.20,"fim":"Ago/27","prog":42},
    "Versato":        {"cod":"—",        "cod_instalacao":None,     "end":"Brasília-DF",      "tarifa_neo":1.03640,"tarifa_mtec":0.82912,"desconto":0.20,"fim":"Ago/27","prog":42},
}
COD_INSTALACAO_PARA_CLIENTE = {v["cod_instalacao"]: k for k, v in CLIENTES_CONFIG.items() if v["cod_instalacao"]}
ORDEM = ["Real Evolution","SQS 314","Oasis Design","Bello Trigo","Versato"]

HISTORICO_ECONOMIA = {
    "Real Evolution":[
        {"mes":"Dez/24","economia":11845.42},
        {"mes":"Jan/25","economia":10106.64},
        {"mes":"Fev/25","economia":11597.03},
        {"mes":"Mar/25","economia":10230.84},
        {"mes":"Mai/25","economia":10727.64},
        {"mes":"Jun/25","economia":11969.62},
        {"mes":"Jul/25","economia":9982.45},
        {"mes":"Ago/25","economia":11597.03},
        {"mes":"Set/25","economia":11969.62},
        {"mes":"Out/25","economia":10851.84},
        {"mes":"Nov/25","economia":10851.84},
        {"mes":"Dez/25","economia":10851.84},
        {"mes":"Jan/26","economia":10851.84},
        {"mes":"Fev/26","economia":9734.05},
        {"mes":"Mar/26","economia":11597.03},
        {"mes":"Abr/26","economia":10727.64},
        {"mes":"Mai/26","economia":10727.64},
    ],
    "SQS 314":[
        {"mes":"Mai/24","economia":2122.23},
        {"mes":"Jun/24","economia":1933.77},
        {"mes":"Jul/24","economia":1860.02},
        {"mes":"Ago/24","economia":2269.72},
        {"mes":"Set/24","economia":2146.81},
        {"mes":"Out/24","economia":1991.13},
        {"mes":"Nov/24","economia":2105.84},
        {"mes":"Dez/24","economia":2523.73},
        {"mes":"Jan/25","economia":2564.7},
        {"mes":"Fev/25","economia":2105.84},
        {"mes":"Mar/25","economia":2376.24},
        {"mes":"Abr/25","economia":2171.39},
        {"mes":"Mai/25","economia":2540.12},
    ],
    "Oasis Design":[
        {"mes":"Mai/25","economia":14910.68},
        {"mes":"Jun/25","economia":15033.52},
        {"mes":"Jul/25","economia":14296.44},
        {"mes":"Ago/25","economia":15402.07},
        {"mes":"Set/25","economia":16753.4},
        {"mes":"Out/25","economia":13129.38},
        {"mes":"Nov/25","economia":13743.62},
        {"mes":"Dez/25","economia":16016.31},
        {"mes":"Jan/26","economia":17981.88},
        {"mes":"Fev/26","economia":16937.67},
        {"mes":"Mar/26","economia":17613.33},
        {"mes":"Abr/26","economia":16814.82},
        {"mes":"Mai/26","economia":15647.76},
    ],
    "Bello Trigo":[
        {"mes":"Ago/25","economia":7945.89},
        {"mes":"Set/25","economia":10786.96},
        {"mes":"Out/25","economia":10357.9},
        {"mes":"Nov/25","economia":10293.58},
        {"mes":"Dez/25","economia":10811.27},
        {"mes":"Jan/26","economia":11265.44},
        {"mes":"Fev/26","economia":10535.17},
        {"mes":"Mar/26","economia":11332.9},
        {"mes":"Abr/26","economia":9982.17},
        {"mes":"Mai/26","economia":12190.24},
    ],
    "Versato":[
        {"mes":"Nov/25","economia":9203.23},
        {"mes":"Dez/25","economia":10662.48},
        {"mes":"Jan/26","economia":10994.13},
        {"mes":"Fev/26","economia":10065.52},
        {"mes":"Mar/26","economia":11856.42},
        {"mes":"Abr/26","economia":10397.16},
        {"mes":"Mai/26","economia":8805.25},
    ],
}

ESTADO_INICIAL = {
    "ref_mes":"Mai/26","atualizado_em":"2026-06-27",
    "clientes":{
        "Real Evolution":{"consumo_faturavel":13820,"saldo_creditos":13820,"ref_mes":"Mai/26"},
        "SQS 314":       {"consumo_faturavel":3100, "saldo_creditos":3100, "ref_mes":"Mai/25"},
        "Oasis Design":  {"consumo_faturavel":20380,"saldo_creditos":20380,"ref_mes":"Mai/26"},
        "Bello Trigo":   {"consumo_faturavel":15541,"saldo_creditos":15541,"ref_mes":"Mai/26"},
        "Versato":       {"consumo_faturavel":10620,"saldo_creditos":10620,"ref_mes":"Mai/26"},
    },
}

# Base fixa: acumulado histórico já faturado até o fim da planilha (Mai/26),
# por cliente. Soma-se a isso o que entrar via relatórios emitidos depois desse ponto.
ACUMULADO_BASE_PLANILHA = 750899.45

# Base fixa: histórico mensal consolidado já fechado na planilha (até Mai/26).
# Meses emitidos via relatório depois disso são adicionados/atualizados por cima.
HISTORICO_MENSAL_BASE = [
    {"mes":"Mai/24","total":2688.01},
    {"mes":"Jun/24","total":2458.18},
    {"mes":"Jul/24","total":2368.25},
    {"mes":"Ago/24","total":2867.88},
    {"mes":"Set/24","total":2717.99},
    {"mes":"Out/24","total":2528.13},
    {"mes":"Nov/24","total":2668.02},
    {"mes":"Dez/24","total":18081.46},
    {"mes":"Jan/25","total":15957.95},
    {"mes":"Fev/25","total":17261.33},
    {"mes":"Mar/25","total":15883.36},
    {"mes":"Abr/25","total":2747.97},
    {"mes":"Mai/25","total":35438.53},
    {"mes":"Jun/25","total":33946.94},
    {"mes":"Jul/25","total":30541.61},
    {"mes":"Ago/25","total":43972.28},
    {"mes":"Set/25","total":49678.53},
    {"mes":"Out/25","total":43214.94},
    {"mes":"Nov/25","total":55510.02},
    {"mes":"Dez/25","total":60822.06},
    {"mes":"Jan/26","total":64261.29},
    {"mes":"Fev/26","total":59485.2},
    {"mes":"Mar/26","total":65894.28},
    {"mes":"Abr/26","total":60296.94},
    {"mes":"Mai/26","total":59608.31},
]

# ── Supabase: estado base (config persistente, não financeiro) ─
def carregar_base() -> dict:
    """Busca a configuração base de cada cliente (consumo/saldo herdado da planilha
    ou do último relatório emitido). Não contém números agregados — esses são calculados."""
    try:
        res = sb.table("dashboard_estado").select("*").eq("id", 1).single().execute()
        if res.data:
            return {"clientes": res.data["clientes"]}
    except Exception:
        pass

    sb.table("dashboard_estado").insert({
        "id":       1,
        "clientes": ESTADO_INICIAL["clientes"],
    }).execute()
    return {"clientes": ESTADO_INICIAL["clientes"]}

def salvar_base(clientes: dict):
    sb.table("dashboard_estado").upsert({"id": 1, "clientes": clientes}).execute()

def listar_relatorios_emitidos() -> list:
    """Todos os registros da tabela de log, mais recentes primeiro."""
    res = sb.table("relatorios_emitidos").select("*").order("emitido_em", desc=True).execute()
    return res.data or []

def ultimos_relatorios_por_cliente(relatorios: list) -> dict:
    """Reduz a lista completa ao registro mais recente de cada cliente."""
    out = {}
    for r in relatorios:  # já vem ordenado desc por emitido_em
        if r["cliente"] not in out:
            out[r["cliente"]] = r
    return out

MESES_PT_IDX = {m:i for i,m in enumerate(["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"])}
def mes_sort_key(label: str):
    p = label.split("/")
    return int("20"+p[1])*100 + MESES_PT_IDX.get(p[0], 0)

def carregar() -> dict:
    """Monta o estado completo do dashboard, calculado dinamicamente:
    - clientes: dados de contrato (planilha) + override do último relatório emitido
    - faturamento_mes / consumo_mes_kwh: soma dos relatórios emitidos no mês de referência atual
    - acumulado_historico: base da planilha + soma de TODOS os relatórios emitidos
    - historico_mensal: base da planilha, com os meses pós-planilha atualizados pelos relatórios
    """
    base       = carregar_base()
    relatorios = listar_relatorios_emitidos()
    ultimos    = ultimos_relatorios_por_cliente(relatorios)

    # Mês de referência atual = mês mais recente com relatório emitido, senão o último da planilha
    if relatorios:
        ref_mes_atual = max(relatorios, key=lambda r: mes_sort_key(r["ref_mes"]))["ref_mes"]
    else:
        ref_mes_atual = ESTADO_INICIAL["ref_mes"]

    # Monta clientes: começa da planilha, sobrepõe com o último relatório de cada um,
    # e por cima disso, se houver fatura pendente de relatório, ela tem prioridade de exibição.
    clientes = {}
    for nome, cfg in base["clientes"].items():
        ult = ultimos.get(nome)
        pendente = cfg.get("pendente_relatorio") and cfg.get("valor_com_desconto") is not None

        if pendente:
            clientes[nome] = {
                "consumo_faturavel": cfg.get("consumo_faturavel"),
                "saldo_creditos":    cfg.get("saldo_creditos"),
                "valor_com_desconto":cfg.get("valor_com_desconto"),
                "ref_mes":           cfg.get("ref_mes"),
                "status":            "ativo",
                "data_relatorio":    None,
                "vencimento_fatura": cfg.get("vencimento_fatura"),
                "aguardando_emissao":True,
            }
        elif ult:
            clientes[nome] = {
                "consumo_faturavel": ult["consumo_kwh"],
                "saldo_creditos":    ult["saldo_creditos"],
                "valor_com_desconto":ult["valor_cobrado"],
                "ref_mes":           ult["ref_mes"],
                "status":            "ativo",
                "data_relatorio":    ult["emitido_em"],
                "vencimento_fatura": ult.get("vencimento_fatura"),
                "aguardando_emissao":False,
            }
        else:
            clientes[nome] = {
                "consumo_faturavel": cfg.get("consumo_faturavel"),
                "saldo_creditos":    cfg.get("saldo_creditos"),
                "valor_com_desconto":None,
                "ref_mes":           cfg.get("ref_mes"),
                "status":            "ativo",
                "data_relatorio":    None,
                "vencimento_fatura": None,
                "aguardando_emissao":False,
            }

    # Faturamento e consumo do mês = soma dos relatórios cujo ref_mes é o mês atual
    do_mes = [r for r in relatorios if r["ref_mes"] == ref_mes_atual]
    faturamento_mes = round(sum(r["valor_cobrado"] for r in do_mes), 2)
    consumo_mes_kwh = sum(r["consumo_kwh"] for r in do_mes)

    # Acumulado histórico = base da planilha + tudo que já foi emitido (todos os meses, todos os clientes)
    acumulado_historico = round(ACUMULADO_BASE_PLANILHA + sum(r["valor_cobrado"] for r in relatorios), 2)

    # Histórico mensal = base da planilha, com meses pós-base recalculados pelos relatórios reais
    por_mes = {}
    for r in relatorios:
        por_mes.setdefault(r["ref_mes"], 0)
        por_mes[r["ref_mes"]] += r["valor_cobrado"]

    hist = [dict(h) for h in HISTORICO_MENSAL_BASE]
    meses_base = {h["mes"] for h in hist}
    for mes, total in por_mes.items():
        if mes in meses_base:
            # Mês já existe na base (ex: Mai/26 reemitido) — substitui pelo valor real dos relatórios
            for h in hist:
                if h["mes"] == mes:
                    h["total"] = round(total, 2)
        else:
            hist.append({"mes": mes, "total": round(total, 2)})
    hist.sort(key=lambda h: mes_sort_key(h["mes"]))

    return {
        "ref_mes":             ref_mes_atual,
        "atualizado_em":       datetime.now().strftime("%d/%m/%Y %H:%M"),
        "faturamento_mes":     faturamento_mes,
        "consumo_mes_kwh":     consumo_mes_kwh,
        "acumulado_historico": acumulado_historico,
        "clientes":            clientes,
        "historico_mensal":    hist,
    }

def registrar_relatorio(cliente: str, ref_mes: str, valor: float, economia: float, consumo: int, saldo: int, vencimento_fatura: str = None):
    """Insere um registro na tabela de log de relatórios emitidos."""
    sb.table("relatorios_emitidos").insert({
        "cliente":           cliente,
        "ref_mes":           ref_mes,
        "valor_cobrado":     valor,
        "economia":          economia,
        "consumo_kwh":       consumo,
        "saldo_creditos":    saldo,
        "vencimento_fatura": vencimento_fatura,
        "emitido_em":        datetime.now().isoformat(),
    }).execute()

# ── Extração PDF ──────────────────────────────────────────────
def extrair_pdf(conteudo_bytes: bytes) -> dict:
    with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
        texto = pdf.pages[0].extract_text()
    texto_norm = re.sub(r'Sal\s+do', 'Saldo', texto)
    texto_norm = re.sub(r'Sa\s+ldo', 'Saldo', texto_norm)

    d = {}
    m = re.search(r'REF:MÊS/ANO\s+TOTAL A PAGAR R\$\s+VENCIMENTO\s+(\d{2}/\d{4})\s+([\d\.]+,\d{2})\s+(\d{2}/\d{2}/\d{4})', texto_norm)
    if m:
        d["ref_mes"] = m.group(1)
        d["total_neoenergia"] = m.group(2)
        d["vencimento"] = m.group(3)

    m = re.search(r'creditos utilizados\s+([\d]+[,.]?\d*)\s*kWh', texto_norm, re.IGNORECASE)
    if m:
        d["creditos_utilizados"] = int(float(m.group(1).replace(',','.')))

    m = re.search(r'Saldo para o proximo ciclo\s+([\d]+[,.]?\d*)\s*kWh', texto_norm, re.IGNORECASE)
    if m:
        d["saldo_proximo_ciclo"] = int(float(m.group(1).replace(',','.')))

    m = re.search(r'CÓDIGO DA INSTALAÇÃO\s*(\d{4,8})', texto_norm)
    if m:
        d["cod_instalacao"] = m.group(1)

    m = re.search(r'(\d{6,7})\s+chave', texto_norm)
    d["cod_cliente"] = m.group(1) if m else None

    return d

def calcular(dados: dict, cfg: dict) -> dict:
    cred = dados["creditos_utilizados"]
    fat  = cred - 100
    vs   = round(cred * cfg["tarifa_neo"],  2)
    vc   = round(fat  * cfg["tarifa_mtec"], 2)
    return {
        "consumo_faturavel":  fat,
        "valor_sem_desconto": vs,
        "valor_com_desconto": vc,
        "saldo_creditos":     dados["saldo_proximo_ciclo"],
        "ref_mes":            dados.get("ref_mes"),
        "total_neoenergia":   dados.get("total_neoenergia"),
        "vencimento":         dados.get("vencimento"),
    }

MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
def ref_label(ref: str) -> str:
    p = ref.split("/")
    return f"{MESES_PT[int(p[0])-1]}/{p[1][2:]}"

# ── Geração PDF ───────────────────────────────────────────────
def gerar_relatorio_pdf(cliente: str, observacoes: str = "") -> bytes:
    from weasyprint import HTML
    base = carregar_base()
    c    = base["clientes"].get(cliente)
    cfg  = CLIENTES_CONFIG.get(cliente)
    if not c or not cfg or not c.get("pendente_relatorio") or c.get("valor_com_desconto") is None:
        raise ValueError("Nenhuma fatura processada aguardando relatório para este cliente. Carregue a fatura primeiro.")

    mes        = c.get("ref_mes","—")
    creditos   = c.get("creditos_utilizados") or (c["consumo_faturavel"] + 100)
    faturavel  = c["consumo_faturavel"]
    tarifa_neo = c.get("tarifa_neo") or cfg["tarifa_neo"]
    vs         = c["valor_sem_desconto"]
    vc         = c["valor_com_desconto"]
    economia   = round(vs - vc, 2)
    saldo      = c["saldo_creditos"]
    desconto   = int(cfg["desconto"] * 100)

    hist     = HISTORICO_ECONOMIA.get(cliente, [])
    hist_rel = [h for h in hist if h["mes"] != mes]
    hist_rel.append({"mes": mes, "economia": economia})
    hist_rel = hist_rel[-10:]

    BRL = lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

    max_val = max((h["economia"] for h in hist_rel), default=1)
    bw, sp  = 38, 12
    chart_w = len(hist_rel) * (bw + sp) + sp
    chart_h = 180
    bars    = ""
    for i, h in enumerate(hist_rel):
        x     = sp + i * (bw + sp)
        bh    = int((h["economia"] / max_val) * 130)
        y     = chart_h - bh - 28
        color = "#5a9a1f" if h["mes"] == mes else "#8dc63f"
        bars += f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="3" fill="{color}"/>'
        bars += f'<text x="{x+bw//2}" y="{chart_h-10}" text-anchor="middle" font-size="9" fill="#666">{h["mes"]}</text>'
        val_fmt = f'{int(h["economia"]):,}'.replace(",",".")
        bars += f'<text x="{x+bw//2}" y="{y-4}" text-anchor="middle" font-size="9" font-weight="bold" fill="{color}">{val_fmt}</text>'

    chart_svg = f'<svg width="{chart_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg">{bars}</svg>'

    obs_html = ""
    if observacoes and observacoes.strip():
        paragrafos = "".join(f"<p>{p.strip()}</p>" for p in observacoes.strip().split("\n") if p.strip())
        obs_html = f"""<div class="section-title">4. OBSERVAÇÕES</div>
        <div class="obs">{paragrafos}</div><div class="divider"></div>"""

    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;color:#333;font-size:13px}}
.page{{padding:36px 44px;max-width:720px;margin:0 auto}}
.header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}}
.logo-circle{{width:60px;height:60px;background:#8dc63f;border-radius:50%;display:flex;align-items:center;justify-content:center}}
.logo-txt{{font-size:26px;font-weight:bold;color:white}}
.header-right{{text-align:right;font-size:11px;color:#888;line-height:1.7}}
h1{{font-size:21px;font-weight:bold;color:#333;text-align:center;margin-bottom:3px}}
.subtitle{{text-align:center;color:#888;font-size:13px;margin-bottom:28px}}
.section-title{{font-size:14px;font-weight:bold;color:#333;border-bottom:3px solid #8dc63f;padding-bottom:5px;margin-bottom:12px;margin-top:24px}}
.formula{{text-align:center;font-size:13px;color:#555;margin-bottom:7px}}
.formula strong{{color:#222}}
.divider{{border:none;border-top:1px solid #e0e0e0;margin:20px 0}}
.resumo-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.resumo-item{{padding:9px 0;border-bottom:1px solid #eee}}
.resumo-label{{font-size:11px;color:#888;margin-bottom:2px}}
.resumo-valor{{font-size:15px;font-weight:bold;color:#333}}
.resumo-valor.green{{color:#5a9a1f}}.resumo-valor.blue{{color:#2a6db5}}
.obs{{background:#f9f9f9;border-left:3px solid #8dc63f;padding:11px 15px;font-size:12px;color:#555;line-height:1.7;margin-top:8px}}
.obs p{{margin-bottom:6px}}.obs p:last-child{{margin-bottom:0}}
.chart-wrap{{overflow-x:auto;margin-top:4px}}
.footer{{margin-top:36px;text-align:center;font-size:11px;color:#aaa;line-height:1.7}}
</style></head><body><div class="page">
<div class="header">
  <div class="logo-circle"><span class="logo-txt">P</span></div>
  <div class="header-right">Asa Sul CLS 312 Bloco D loja 34<br>Brasília - DF, 70365-540<br>mtecenergia.com.br · (61) 3465-3366</div>
</div>
<h1>Relatório de Créditos - {cliente}</h1>
<p class="subtitle">{mes.upper()}</p>
<div class="section-title">1. FATURA COM A NEOENERGIA</div>
<p class="formula">Consumo x Tarifa da Neoenergia = Valor a pagar</p>
<p class="formula">{creditos:,} x {tarifa_neo:.5f} = <strong>{BRL(vs)}</strong></p>
<div class="divider"></div>
<div class="section-title">2. FATURA COM A PATUÁ</div>
<p class="formula">Consumo x Tarifa da Neoenergia x Desconto = Valor a pagar</p>
<p class="formula">{faturavel:,} x {tarifa_neo:.5f} x (1-{desconto}%) = <strong>{BRL(vc)}</strong></p>
<div class="divider"></div>
<div class="section-title">3. RESUMO GERAL</div>
<div class="resumo-grid">
  <div class="resumo-item"><div class="resumo-label">Saldo de créditos</div><div class="resumo-valor blue">{saldo:,} kWh</div></div>
  <div class="resumo-item"><div class="resumo-label">Créditos cobrados</div><div class="resumo-valor">{faturavel:,} kWh</div></div>
  <div class="resumo-item"><div class="resumo-label">Valor a ser pago</div><div class="resumo-valor">{BRL(vc)}</div></div>
  <div class="resumo-item"><div class="resumo-label">Economia</div><div class="resumo-valor green">{BRL(economia)}</div></div>
</div>
<div class="divider"></div>
{obs_html}
<div class="section-title">5. ECONOMIA</div>
<p style="font-size:11px;color:#888;margin-bottom:8px">Reais (R$)</p>
<div class="chart-wrap">{chart_svg}</div>
<div class="footer">Asa Sul CLS 312 Bloco D loja 34 - Asa Sul, Brasília - DF, 70365-540<br>mtecenergia.com.br · (61) 3465-3366</div>
</div></body></html>"""

    return HTML(string=html).write_pdf()

# ── API ───────────────────────────────────────────────────────
@app.get("/api/dados")
def api_dados():
    return JSONResponse(carregar())

@app.post("/api/upload")
async def api_upload(cliente: str = Form(...), fatura: UploadFile = File(...)):
    if cliente not in CLIENTES_CONFIG:
        raise HTTPException(400, f"Cliente '{cliente}' não encontrado")
    if not fatura.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Envie um arquivo PDF")

    conteudo = await fatura.read()
    try:
        dados_pdf = extrair_pdf(conteudo)
    except Exception as e:
        raise HTTPException(422, f"Erro ao ler PDF: {e}")

    if not dados_pdf.get("creditos_utilizados"):
        raise HTTPException(422, "Não foi possível extrair os créditos utilizados. Confirme que é uma fatura Neoenergia Brasília.")
    if not dados_pdf.get("saldo_proximo_ciclo"):
        raise HTTPException(422, "Não foi possível extrair o saldo de créditos. Verifique o PDF.")

    # ── Validação cruzada: a fatura pertence mesmo ao cliente selecionado? ──
    cfg = CLIENTES_CONFIG[cliente]
    cod_pdf = dados_pdf.get("cod_instalacao")
    if cfg.get("cod_instalacao") and cod_pdf:
        if cod_pdf != cfg["cod_instalacao"]:
            cliente_correto = COD_INSTALACAO_PARA_CLIENTE.get(cod_pdf)
            if cliente_correto:
                raise HTTPException(
                    422,
                    f"Esta fatura pertence a {cliente_correto} (código de instalação {cod_pdf}), não a {cliente}. "
                    f"Selecione {cliente_correto} ou envie a fatura correta."
                )
            else:
                raise HTTPException(
                    422,
                    f"Esta fatura tem código de instalação {cod_pdf}, que não corresponde a {cliente} "
                    f"(esperado: {cfg['cod_instalacao']}). Verifique o arquivo enviado."
                )

    calc  = calcular(dados_pdf, cfg)
    label = ref_label(calc["ref_mes"])

    base = carregar_base()
    relatorios = listar_relatorios_emitidos()
    ultimo = ultimos_relatorios_por_cliente(relatorios).get(cliente)
    if ultimo and ultimo["ref_mes"] == label:
        raise HTTPException(409, f"Já existe um relatório emitido para {cliente} em {label}. Para reprocessar, exclua o relatório existente no histórico primeiro.")

    # Salva a fatura processada como "pendente de relatório" no buffer (dashboard_estado.clientes)
    base["clientes"][cliente] = {
        "consumo_faturavel": calc["consumo_faturavel"],
        "saldo_creditos":    calc["saldo_creditos"],
        "ref_mes":           label,
        "valor_sem_desconto":calc["valor_sem_desconto"],
        "valor_com_desconto":calc["valor_com_desconto"],
        "creditos_utilizados":dados_pdf["creditos_utilizados"],
        "tarifa_neo":        cfg["tarifa_neo"],
        "vencimento_fatura": calc.get("vencimento"),
        "pendente_relatorio":True,
    }
    salvar_base(base["clientes"])

    return {
        "ok": True, "cliente": cliente, "ref_mes": label,
        "consumo_faturavel":  calc["consumo_faturavel"],
        "valor_sem_desconto": calc["valor_sem_desconto"],
        "valor_com_desconto": calc["valor_com_desconto"],
        "saldo_creditos":     calc["saldo_creditos"],
        "total_neoenergia":   calc["total_neoenergia"],
        "vencimento":         calc["vencimento"],
    }

@app.post("/api/relatorio")
async def api_relatorio(cliente: str = Form(...), observacoes: str = Form("")):
    if cliente not in CLIENTES_CONFIG:
        raise HTTPException(400, f"Cliente '{cliente}' não encontrado")

    base = carregar_base()
    c    = base["clientes"].get(cliente, {})
    if not c.get("pendente_relatorio") or c.get("valor_com_desconto") is None:
        raise HTTPException(422, f"Nenhuma fatura processada aguardando relatório para {cliente}. Carregue a fatura primeiro.")

    try:
        pdf_bytes = gerar_relatorio_pdf(cliente, observacoes)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar PDF: {e}")

    # ── Registro permanente do relatório emitido (fonte única de verdade) ──
    economia = round((c["valor_sem_desconto"] or 0) - (c["valor_com_desconto"] or 0), 2)
    registrar_relatorio(
        cliente           = cliente,
        ref_mes           = c.get("ref_mes","—"),
        valor             = c.get("valor_com_desconto") or 0,
        economia          = economia,
        consumo           = c.get("consumo_faturavel") or 0,
        saldo             = c.get("saldo_creditos") or 0,
        vencimento_fatura = c.get("vencimento_fatura"),
    )

    # Limpa o buffer: a fatura deixa de estar "pendente" pois virou relatório oficial
    c["pendente_relatorio"] = False
    base["clientes"][cliente] = c
    salvar_base(base["clientes"])

    nome_arquivo = f"Relatorio_{cliente.replace(' ','_')}_{datetime.now().strftime('%Y%m')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'}
    )

@app.get("/api/historico-relatorios")
def api_historico_relatorios():
    """Retorna apenas o relatório mais recente de cada cliente (evita lista infinita)."""
    relatorios = listar_relatorios_emitidos()
    ultimos = ultimos_relatorios_por_cliente(relatorios)
    out = sorted(ultimos.values(), key=lambda r: r["emitido_em"], reverse=True)
    return JSONResponse(out)

@app.delete("/api/historico-relatorios/{relatorio_id}")
def api_excluir_relatorio(relatorio_id: int):
    """Exclui um relatório do log. Todos os números do dashboard recalculam automaticamente
    na próxima leitura, pois são derivados ao vivo da tabela relatorios_emitidos."""
    res = sb.table("relatorios_emitidos").select("*").eq("id", relatorio_id).execute()
    if not res.data:
        raise HTTPException(404, "Relatório não encontrado.")
    registro = res.data[0]
    sb.table("relatorios_emitidos").delete().eq("id", relatorio_id).execute()
    return {"ok": True, "cliente": registro["cliente"], "ref_mes": registro["ref_mes"]}

# ── HTML ──────────────────────────────────────────────────────
def html_page(modo: str) -> str:
    is_gestor = modo == "gestor"
    titulo_badge = "Gestor" if is_gestor else "Usina"
    cor_badge    = "#c8860a" if is_gestor else "#2d7a3a"

    upload_html = """
    <section>
      <div class="section-title">Carregar fatura Neoenergia</div>
      <div class="upload-card">
        <div class="upload-top">
          <div>
            <select id="sel-cliente">
              <option value="">Selecione o cliente...</option>
              <option>Real Evolution</option><option>SQS 314</option>
              <option>Oasis Design</option><option>Bello Trigo</option><option>Versato</option>
            </select>
            <label class="file-btn" for="file-input"><span id="file-label-txt">Escolher PDF</span></label>
            <input type="file" id="file-input" accept=".pdf" style="display:none">
            <span id="file-name" class="file-name">Nenhum arquivo</span>
          </div>
          <button id="btn-enviar" onclick="enviarFatura()">Processar fatura</button>
        </div>
        <div id="upload-resultado" class="upload-resultado" style="display:none"></div>
      </div>
    </section>
    <section>
      <div class="section-title">Gerar relatório mensal</div>
      <div class="upload-card">
        <div class="upload-top">
          <div>
            <select id="sel-cliente-rel">
              <option value="">Selecione o cliente...</option>
              <option>Real Evolution</option><option>SQS 314</option>
              <option>Oasis Design</option><option>Bello Trigo</option><option>Versato</option>
            </select>
          </div>
          <button id="btn-relatorio" onclick="gerarRelatorio()">Baixar relatório PDF</button>
        </div>
        <div style="margin-top:12px">
          <label style="font-size:11px;color:#9a9a94;font-weight:600;letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:6px">
            Observações (opcional — seção 4 do relatório)
          </label>
          <textarea id="txt-obs" rows="3"
            placeholder="Ex: Prezado cliente, informamos que..."
            style="width:100%;border:1px solid #e4e4e0;border-radius:8px;padding:10px 12px;
            font-size:13px;font-family:inherit;resize:vertical;outline:none;color:#1a1a18"></textarea>
        </div>
        <div id="rel-resultado" class="upload-resultado" style="display:none"></div>
      </div>
    </section>
    <section>
      <div class="section-title">Histórico de relatórios emitidos</div>
      <div class="tbl-wrap"><table>
        <thead><tr>
          <th>Cliente</th><th>Mês ref.</th><th class="r">Valor cobrado</th>
          <th class="r">Consumo</th><th>Emitido em</th><th class="r">Ação</th>
        </tr></thead>
        <tbody id="tbody-hist"></tbody>
      </table></div>
    </section>
    """ if is_gestor else ""

    gestor_js = r"""
document.getElementById("file-input").addEventListener("change", function() {
  document.getElementById("file-name").textContent = this.files[0]?.name || "Nenhum arquivo";
  document.getElementById("file-label-txt").textContent = "PDF selecionado ✓";
});
async function enviarFatura() {
  const cliente = document.getElementById("sel-cliente").value;
  const file    = document.getElementById("file-input").files[0];
  const btn     = document.getElementById("btn-enviar");
  const res     = document.getElementById("upload-resultado");
  if (!cliente) { alert("Selecione um cliente."); return; }
  if (!file)    { alert("Selecione o arquivo PDF."); return; }
  btn.disabled = true; btn.textContent = "Processando..."; res.style.display = "none";
  const form = new FormData();
  form.append("cliente", cliente); form.append("fatura", file);
  try {
    const r = await fetch("/api/upload", { method:"POST", body: form });
    const rj = await r.json();
    if (!r.ok) {
      res.className = "upload-resultado res-err";
      res.innerHTML = "<strong>Erro:</strong> " + (rj.detail || "Falha no processamento.");
    } else {
      res.className = "upload-resultado res-ok";
      const brl = v => "R$ " + v.toLocaleString("pt-BR",{minimumFractionDigits:2});
      res.innerHTML = `<strong>✓ ${rj.cliente} — ${rj.ref_mes} processado com sucesso</strong>
        <div style="margin-top:10px">
          <div class="res-row"><span class="res-label">Consumo faturável</span><span class="res-val">${rj.consumo_faturavel.toLocaleString("pt-BR")} kWh</span></div>
          <div class="res-row"><span class="res-label">Valor com desconto</span><span class="res-val">${brl(rj.valor_com_desconto)}</span></div>
          <div class="res-row"><span class="res-label">Saldo de créditos</span><span class="res-val">${rj.saldo_creditos.toLocaleString("pt-BR")} kWh</span></div>
          <div class="res-row"><span class="res-label">Fatura Neoenergia</span><span class="res-val">R$ ${rj.total_neoenergia} · vence ${rj.vencimento}</span></div>
        </div>`;
      await carregar();
    }
    res.style.display = "block";
  } catch(e) {
    res.className = "upload-resultado res-err";
    res.innerHTML = "Erro de conexão: " + e.message;
    res.style.display = "block";
  }
  btn.disabled = false; btn.textContent = "Processar fatura";
}
async function gerarRelatorio() {
  const cliente = document.getElementById("sel-cliente-rel").value;
  const obs     = document.getElementById("txt-obs").value;
  const btn     = document.getElementById("btn-relatorio");
  const res     = document.getElementById("rel-resultado");
  if (!cliente) { alert("Selecione um cliente."); return; }
  btn.disabled = true; btn.textContent = "Gerando PDF..."; res.style.display = "none";
  const form = new FormData();
  form.append("cliente", cliente); form.append("observacoes", obs);
  try {
    const r = await fetch("/api/relatorio", { method:"POST", body: form });
    if (!r.ok) {
      const rj = await r.json();
      res.className = "upload-resultado res-err";
      res.innerHTML = "<strong>Erro:</strong> " + (rj.detail || "Falha ao gerar PDF.");
    } else {
      const blob = await r.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url; a.download = `Relatorio_${cliente.replace(/ /g,"_")}.pdf`; a.click();
      URL.revokeObjectURL(url);
      res.className = "upload-resultado res-ok";
      res.innerHTML = "✓ Relatório gerado e download iniciado.";
      await carregar();
      await carregarHistorico();
    }
    res.style.display = "block";
  } catch(e) {
    res.className = "upload-resultado res-err";
    res.innerHTML = "Erro de conexão: " + e.message;
    res.style.display = "block";
  }
  btn.disabled = false; btn.textContent = "Baixar relatório PDF";
}
async function carregarHistorico() {
  const r = await fetch("/api/historico-relatorios");
  const rows = await r.json();
  const brl = v => "R$ " + Number(v).toLocaleString("pt-BR",{minimumFractionDigits:2});
  const kwh = v => Number(v).toLocaleString("pt-BR") + " kWh";
  let html = "";
  if (!rows.length) {
    html = `<tr><td colspan="6" style="text-align:center;color:#9a9a94;padding:20px">Nenhum relatório emitido ainda.</td></tr>`;
  } else {
    for (const row of rows) {
      const dt = new Date(row.emitido_em);
      const fmt = dt.toLocaleDateString("pt-BR") + " " + dt.toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"});
      html += `<tr>
        <td><span class="cn">${row.cliente}</span></td>
        <td>${row.ref_mes}</td>
        <td class="r"><span class="vd">${brl(row.valor_cobrado)}</span></td>
        <td class="r">${kwh(row.consumo_kwh)}</td>
        <td>${fmt}</td>
        <td class="r"><button class="btn-excluir-rel" onclick="excluirRelatorio(${row.id})" title="Excluir relatório">Excluir</button></td>
      </tr>`;
    }
  }
  document.getElementById("tbody-hist").innerHTML = html;
}
async function excluirRelatorio(id) {
  if (!confirm("Excluir este relatório? O cliente ficará liberado para reprocessar a fatura.")) return;
  try {
    const r = await fetch(`/api/historico-relatorios/${id}`, { method: "DELETE" });
    if (!r.ok) {
      const rj = await r.json();
      alert("Erro: " + (rj.detail || "Falha ao excluir."));
      return;
    }
    await carregarHistorico();
    await carregar();
  } catch(e) {
    alert("Erro de conexão: " + e.message);
  }
}
carregarHistorico();
""" if is_gestor else ""

    ABREV_JS = '{"Real Evolution":"Real Evo.","SQS 314":"SQS 314","Oasis Design":"Oasis","Bello Trigo":"Bello Trigo","Versato":"Versato"}'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Patuá Solar</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#f5f5f3;--surf:#fff;--bord:#e4e4e0;--bord-s:#c8c8c2;--txt:#1a1a18;--txt3:#9a9a94;
  --sol:#c8860a;--sol-bg:#fef3d8;--sol-bord:#f0c96a;--grn:#2d7a3a;--grn-bg:#e8f5eb;--r:10px;}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--txt);padding-bottom:48px}}
header{{background:var(--surf);border-bottom:1px solid var(--bord);padding:16px 28px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}}
.logo{{display:flex;align-items:center;gap:10px}}
.logo-ico{{width:30px;height:30px;background:var(--sol);border-radius:8px;display:flex;align-items:center;justify-content:center}}
.logo-ico svg{{width:16px;height:16px;fill:#fff}}
.logo-name{{font-size:14px;font-weight:600;letter-spacing:-.3px}}
.logo-sub{{font-size:11px;color:var(--txt3);margin-top:1px}}
.badges{{display:flex;align-items:center;gap:8px}}
.badge{{font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px}}
.badge-mes{{background:var(--sol-bg);border:1px solid var(--sol-bord);color:var(--sol)}}
.badge-modo{{color:#fff;background:{cor_badge}}}
.atualiz{{font-size:10px;color:var(--txt3)}}
main{{padding:24px 28px 0;max-width:1280px;margin:0 auto}}
section{{margin-bottom:28px}}
.section-title{{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--txt3);margin-bottom:12px}}
.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:28px}}
.mc{{background:var(--surf);border:1px solid var(--bord);border-radius:var(--r);padding:16px 18px}}
.mc.hi{{border-color:var(--sol-bord);background:var(--sol-bg)}}
.mc-label{{font-size:11px;color:var(--txt3);font-weight:500;margin-bottom:5px}}
.mc-val{{font-size:24px;font-weight:700;letter-spacing:-.8px;line-height:1}}
.mc.hi .mc-val{{color:var(--sol)}}
.mc-sub{{font-size:11px;color:var(--txt3);margin-top:5px}}
.tbl-wrap{{background:var(--surf);border:1px solid var(--bord);border-radius:var(--r);overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
thead{{background:#fafaf8}}
th{{text-align:left;font-size:11px;font-weight:600;color:var(--txt3);
  letter-spacing:.05em;text-transform:uppercase;padding:11px 14px;
  border-bottom:1px solid var(--bord);white-space:nowrap}}
th.r,td.r{{text-align:right}}
td{{padding:12px 14px;font-size:13px;border-bottom:1px solid var(--bord);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fafaf8}}
.cn{{font-weight:600;font-size:13px}}
.cc{{font-size:11px;color:var(--txt3);margin-top:1px}}
.vd{{font-weight:700;font-size:14px}}
.note{{display:inline-block;font-size:10px;color:var(--txt3);background:#f0f0ec;border-radius:4px;padding:1px 7px;font-style:italic}}
.dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}}
.dg{{background:var(--grn)}}.da{{background:var(--sol)}}.dr{{background:#8dc63f}}
.tfoot td{{background:#fafaf8;font-weight:700;font-size:13px;border-top:2px solid var(--bord-s);border-bottom:none}}
.bottom{{display:grid;grid-template-columns:1fr 320px;gap:18px;align-items:start}}
.chart-card{{background:var(--surf);border:1px solid var(--bord);border-radius:var(--r);padding:20px}}
.chart-title{{font-size:14px;font-weight:600;margin-bottom:3px}}
.chart-sub{{font-size:11px;color:var(--txt3);margin-bottom:16px}}
.chart-wrap{{position:relative;height:210px}}
.clist{{display:flex;flex-direction:column;gap:9px}}
.cc2{{background:var(--surf);border:1px solid var(--bord);border-radius:var(--r);padding:11px 13px}}
.cc2.alert{{border-color:var(--sol-bord)}}
.ct{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px}}
.ct-name{{font-size:12px;font-weight:600}}
.ct-date{{font-size:11px;color:var(--txt3)}}
.ct-date.warn{{color:var(--sol)}}
.pb{{height:4px;background:var(--bord);border-radius:2px;overflow:hidden}}
.pf{{height:100%;border-radius:2px}}.pf-ok{{background:#c8d8a8}}.pf-warn{{background:var(--sol)}}
.upload-card{{background:var(--surf);border:1px solid var(--bord);border-radius:var(--r);padding:18px 20px}}
.upload-top{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.upload-top > div{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
select{{height:36px;border:1px solid var(--bord-s);border-radius:8px;padding:0 12px;font-size:13px;
  color:var(--txt);background:var(--surf);outline:none;cursor:pointer;min-width:180px}}
select:focus{{border-color:var(--sol)}}
.file-btn{{display:inline-flex;align-items:center;height:36px;padding:0 14px;border:1px solid var(--bord-s);
  border-radius:8px;font-size:13px;color:var(--txt);cursor:pointer;background:var(--surf);white-space:nowrap}}
.file-btn:hover{{background:#f5f5f3;border-color:var(--sol)}}
.file-name{{font-size:12px;color:var(--txt3)}}
#btn-enviar,#btn-relatorio{{height:36px;padding:0 20px;background:var(--sol);color:#fff;
  border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap}}
#btn-enviar:hover,#btn-relatorio:hover{{background:#a06a06}}
#btn-enviar:disabled,#btn-relatorio:disabled{{background:#ccc;cursor:not-allowed}}
.upload-resultado{{margin-top:14px;padding:14px 16px;border-radius:8px;font-size:13px;line-height:1.6}}
.res-ok{{background:var(--grn-bg);border:1px solid #b8dbbe;color:#1a4a22}}
.res-err{{background:#fdeaea;border:1px solid #f5b8b8;color:#7a1a1a}}
.res-row{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(0,0,0,.06)}}
.res-row:last-child{{border-bottom:none}}
.res-label{{opacity:.75}}.res-val{{font-weight:600}}
.tag-rel{{display:inline-block;font-size:10px;font-weight:600;padding:1px 7px;border-radius:20px;
  background:#e8f5eb;color:#2d7a3a;border:1px solid #b8dbbe}}
.btn-excluir-rel{{font-size:11px;font-weight:600;padding:5px 12px;border-radius:6px;
  border:1px solid #f5b8b8;background:#fdeaea;color:#b03030;cursor:pointer}}
.btn-excluir-rel:hover{{background:#f8d4d4}}
.footer{{text-align:center;font-size:11px;color:var(--txt3);margin-top:32px;padding-top:18px;border-top:1px solid var(--bord)}}
</style></head>
<body>
<header>
  <div class="logo">
    <div class="logo-ico"><svg viewBox="0 0 24 24"><path d="M12 2L14.4 8.4L21 9.3L16.5 13.6L17.8 20.2L12 17L6.2 20.2L7.5 13.6L3 9.3L9.6 8.4L12 2Z"/></svg></div>
    <div><div class="logo-name">Patuá Solar</div><div class="logo-sub">Gestão de Contratos — Mercado Cativo</div></div>
  </div>
  <div class="badges">
    <span class="badge badge-modo">{titulo_badge}</span>
    <span class="badge badge-mes" id="ref-mes">—</span>
    <span class="atualiz" id="atualiz"></span>
  </div>
</header>
<main>
  {upload_html}
  <div class="metrics">
    <div class="mc hi"><div class="mc-label">Faturamento do mês</div><div class="mc-val" id="m-fat">—</div><div class="mc-sub" id="m-fat-sub">—</div></div>
    <div class="mc"><div class="mc-label">Consumo compensado</div><div class="mc-val" id="m-kwh">—</div><div class="mc-sub">kWh no mês</div></div>
    <div class="mc"><div class="mc-label">Acumulado histórico</div><div class="mc-val" id="m-acum">—</div><div class="mc-sub">Total faturado desde o início</div></div>
  </div>
  <section>
    <div class="section-title">Clientes — posição do mês</div>
    <div class="tbl-wrap"><table>
      <thead><tr>
        <th>Cliente</th>
        <th class="r">Faturamento Patuá</th>
        <th class="r">Consumo (kWh)</th>
        <th class="r">Tarifa Mtec</th>
        <th class="r">Saldo créditos</th>
        <th>Vencimento</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
      <tfoot><tr class="tfoot">
        <td>Total</td>
        <td class="r" id="t-com">—</td>
        <td class="r" id="t-kwh">—</td>
        <td class="r">—</td>
        <td class="r" id="t-sal">—</td>
        <td>—</td>
      </tr></tfoot>
    </table></div>
  </section>
  <div class="bottom">
    <div class="chart-card">
      <div class="chart-title">Faturamento mensal consolidado</div>
      <div class="chart-sub">Soma de todos os clientes · valor com desconto (R$)</div>
      <div class="chart-wrap"><canvas id="chart"></canvas></div>
    </div>
    <div>
      <div class="section-title" style="margin-bottom:9px">Vigência dos contratos</div>
      <div class="clist" id="contratos"></div>
    </div>
  </div>
  <div class="footer" id="footer">Patuá Solar · carregando...</div>
</main>
<script>
const CFG = {json.dumps({k:{"cod":v["cod"],"end":v["end"],"tarifa_mtec":v["tarifa_mtec"],"fim":v["fim"],"prog":v["prog"]} for k,v in CLIENTES_CONFIG.items()},ensure_ascii=False)};
const ORDEM = {json.dumps(ORDEM)};
const ABREV = {ABREV_JS};
const BRL = v => v==null?"—":"R$\u00a0"+v.toLocaleString("pt-BR",{{minimumFractionDigits:2,maximumFractionDigits:2}});
const KWH = v => v==null?"—":v.toLocaleString("pt-BR")+" kWh";
const TAR = v => v==null?"—":"R$\u00a0"+v.toFixed(5);
let chart=null;
async function carregar(){{
  const r=await fetch("/api/dados"); const d=await r.json();
  document.getElementById("ref-mes").textContent=d.ref_mes||"—";
  document.getElementById("atualiz").textContent=d.atualizado_em?"Atualizado "+d.atualizado_em:"";
  document.getElementById("m-fat").textContent=BRL(d.faturamento_mes);
  document.getElementById("m-kwh").textContent=(d.consumo_mes_kwh||0).toLocaleString("pt-BR");
  document.getElementById("m-acum").textContent=BRL(d.acumulado_historico);

  const ativos=ORDEM.filter(n=>{{
    const c=d.clientes[n];
    return c && c.ref_mes===d.ref_mes && !c.aguardando_emissao && c.valor_com_desconto!=null;
  }});
  document.getElementById("m-fat-sub").textContent=
    ativos.length ? ativos.map(n=>ABREV[n]||n).join(" · ") : "Nenhum relatório emitido neste mês";

  let tCom=0,tKwh=0,tSal=0,tbody="";
  for(const nome of ORDEM){{
    const c=d.clientes[nome],cf=CFG[nome];
    if(!c||!cf)continue;
    const semFatura=c.valor_com_desconto==null;
    tCom+=c.valor_com_desconto||0;
    tKwh+=c.consumo_faturavel||0;
    tSal+=c.saldo_creditos||0;
    const aguardandoEmissao=c.aguardando_emissao;
    const tagEmissao=aguardandoEmissao?'<span class="note">aguardando emissão</span>':'';
    tbody+=`<tr>
      <td><div class="cn">${{nome}}</div><div class="cc">Cód. ${{cf.cod}} · ${{cf.end}}</div></td>
      <td class="r">${{semFatura?'<span class="note">sem fatura</span>':'<span class="vd">'+BRL(c.valor_com_desconto)+'</span> '+tagEmissao}}</td>
      <td class="r">${{semFatura?"—":(c.consumo_faturavel||0).toLocaleString("pt-BR")}}</td>
      <td class="r">${{TAR(cf.tarifa_mtec)}}</td>
      <td class="r">${{semFatura?"—":KWH(c.saldo_creditos)}}</td>
      <td>${{c.vencimento_fatura||"—"}}</td>
    </tr>`;
  }}
  document.getElementById("tbody").innerHTML=tbody;
  document.getElementById("t-com").textContent=BRL(tCom);
  document.getElementById("t-kwh").textContent=tKwh.toLocaleString("pt-BR")+" kWh";
  document.getElementById("t-sal").textContent=KWH(tSal);

  let chtml="";
  for(const nome of ORDEM){{
    const cf=CFG[nome],warn=cf.prog>=85;
    chtml+=`<div class="cc2${{warn?' alert':''}}">
      <div class="ct"><span class="ct-name">${{nome}}</span>
      <span class="ct-date${{warn?' warn':''}}">` + cf.fim + `</span></div>
      <div class="pb"><div class="pf ${{warn?'pf-warn':'pf-ok'}}" style="width:${{cf.prog}}%"></div></div>
    </div>`;
  }}
  document.getElementById("contratos").innerHTML=chtml;

  const hist=d.historico_mensal||[];
  const labels=hist.map(h=>h.mes),vals=hist.map(h=>h.total);
  const cores=vals.map((_,i)=>i===vals.length-1?"#c8860a":"#e8e8e4");
  const bords=vals.map((_,i)=>i===vals.length-1?"#a06a06":"#d4d4ce");
  if(chart)chart.destroy();
  chart=new Chart(document.getElementById("chart").getContext("2d"),{{
    type:"bar",
    data:{{labels,datasets:[{{data:vals,backgroundColor:cores,borderColor:bords,borderWidth:1,borderRadius:3}}]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>BRL(c.parsed.y)}}}}}},
      scales:{{
        x:{{grid:{{display:false}},ticks:{{font:{{size:9}},color:"#9a9a94",maxRotation:45}}}},
        y:{{grid:{{color:"#f0f0ec"}},border:{{dash:[3,3]}},
          ticks:{{font:{{size:10}},color:"#9a9a94",callback:v=>"R$"+(v/1000).toFixed(0)+"k"}}}}
      }}
    }}
  }});
  document.getElementById("footer").textContent="Patuá Solar · "+(d.atualizado_em||"");
}}
{gestor_js}
carregar();
setInterval(carregar,120000);
</script>
</body></html>"""

@app.get("/gestor",response_class=HTMLResponse)
def pg_gestor(): return HTMLResponse(html_page("gestor"))

@app.get("/usina",response_class=HTMLResponse)
def pg_usina(): return HTMLResponse(html_page("usina"))

@app.get("/")
def root(): return RedirectResponse("/gestor")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
