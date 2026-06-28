"""
Patuá Solar — Sistema Web Completo
====================================
Duas URLs:
  /gestor   → dashboard + upload de faturas (você)
  /usina    → dashboard somente leitura (dono da usina)

Deploy no Render:
  Build command : pip install -r requirements.txt
  Start command : uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import re, json, os, io
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import pdfplumber

app = FastAPI()

# ── Persistência ──────────────────────────────────────────────
DADOS_PATH = Path("data/dashboard.json")
DADOS_PATH.parent.mkdir(exist_ok=True)

CLIENTES_CONFIG = {
    "Real Evolution": {"cod":"2972408-2",  "end":"SQNW 109",        "tarifa_neo":0.97030, "tarifa_mtec":0.77624, "desconto":0.20, "fim":"Jul/27", "prog":68},
    "SQS 314":        {"cod":"3079816-7",  "end":"SQS 314",         "tarifa_neo":0.99926, "tarifa_mtec":0.81939, "desconto":0.18, "fim":"Ago/26", "prog":90},
    "Oasis Design":   {"cod":"3079816",    "end":"Águas Claras",    "tarifa_neo":0.95975, "tarifa_mtec":0.76780, "desconto":0.20, "fim":"Mar/27", "prog":58},
    "Bello Trigo":    {"cod":"3140795",    "end":"Jardim Botânico", "tarifa_neo":0.98049, "tarifa_mtec":0.78439, "desconto":0.20, "fim":"Ago/27", "prog":42},
    "Versato":        {"cod":"—",          "end":"Brasília-DF",     "tarifa_neo":1.03640, "tarifa_mtec":0.82912, "desconto":0.20, "fim":"Ago/27", "prog":42},
}
ORDEM = ["Real Evolution","SQS 314","Oasis Design","Bello Trigo","Versato"]

ESTADO_INICIAL = {
    "ref_mes":"Mai/26", "atualizado_em":"2026-06-27",
    "faturamento_mes":47370.89, "consumo_mes_kwh":60361,
    "acumulado_historico":567782.57,
    "clientes":{
        "Real Evolution": {"consumo_faturavel":13820,"valor_sem_desconto":13506.58,"valor_com_desconto":10727.64,"saldo_creditos":109513,"ref_mes":"Mai/26","status":"ativo"},
        "SQS 314":        {"consumo_faturavel":None, "valor_sem_desconto":None,    "valor_com_desconto":None,    "saldo_creditos":None,  "ref_mes":None,     "status":"aguardando"},
        "Oasis Design":   {"consumo_faturavel":20380,"valor_sem_desconto":19655.68,"valor_com_desconto":15647.76,"saldo_creditos":69713, "ref_mes":"Mai/26","status":"ativo"},
        "Bello Trigo":    {"consumo_faturavel":15541,"valor_sem_desconto":15335.84,"valor_com_desconto":12190.24,"saldo_creditos":26677, "ref_mes":"Mai/26","status":"ativo"},
        "Versato":        {"consumo_faturavel":10620,"valor_sem_desconto":11110.21,"valor_com_desconto":8805.25, "saldo_creditos":68964, "ref_mes":"Mai/26","status":"ativo"},
    },
    "historico_mensal":[
        {"mes":"Mai/24","total":2122},{"mes":"Jun/24","total":1934},
        {"mes":"Jul/24","total":1860},{"mes":"Ago/24","total":2270},
        {"mes":"Set/24","total":2147},{"mes":"Out/24","total":1991},
        {"mes":"Nov/24","total":2106},{"mes":"Dez/24","total":14410},
        {"mes":"Jan/25","total":12671},{"mes":"Fev/25","total":13703},
        {"mes":"Mar/25","total":12607},{"mes":"Abr/25","total":2171},
        {"mes":"Mai/25","total":28178},{"mes":"Jun/25","total":27003},
        {"mes":"Jul/25","total":24279},{"mes":"Ago/25","total":34945},
        {"mes":"Set/25","total":39510},{"mes":"Out/25","total":34339},
        {"mes":"Nov/25","total":44092},{"mes":"Dez/25","total":48342},
        {"mes":"Jan/26","total":51093},{"mes":"Fev/26","total":47272},
        {"mes":"Mar/26","total":52400},{"mes":"Abr/26","total":47922},
        {"mes":"Mai/26","total":47371},
    ],
}

def carregar():
    if DADOS_PATH.exists():
        return json.loads(DADOS_PATH.read_text())
    DADOS_PATH.write_text(json.dumps(ESTADO_INICIAL, ensure_ascii=False, indent=2))
    return ESTADO_INICIAL

def salvar(d):
    DADOS_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2))

# ── Extração PDF ──────────────────────────────────────────────
def extrair_pdf(conteudo_bytes: bytes) -> dict:
    with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
        texto = pdf.pages[0].extract_text()

    d = {}
    m = re.search(r'REF:MÊS/ANO\s+TOTAL A PAGAR R\$\s+VENCIMENTO\s+(\d{2}/\d{4})\s+([\d\.]+,\d{2})\s+(\d{2}/\d{2}/\d{4})', texto)
    if m:
        d["ref_mes"] = m.group(1)
        d["total_neoenergia"] = m.group(2)
        d["vencimento"] = m.group(3)

    m = re.search(r'creditos utilizados\s+(\d+)\s+kWh', texto, re.IGNORECASE)
    d["creditos_utilizados"] = int(m.group(1)) if m else None

    m = re.search(r'Saldo para o proximo ciclo\s+(\d+)\s+kWh', texto, re.IGNORECASE)
    d["saldo_proximo_ciclo"] = int(m.group(1)) if m else None

    m = re.search(r'QD-\s*\d+\s+(\d{6,7})\s+chave', texto)
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

# ── Rotas API ─────────────────────────────────────────────────
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

    cfg    = CLIENTES_CONFIG[cliente]
    calc   = calcular(dados_pdf, cfg)
    label  = ref_label(calc["ref_mes"])

    d = carregar()
    c = d["clientes"][cliente]
    c.update({
        "consumo_faturavel":  calc["consumo_faturavel"],
        "valor_sem_desconto": calc["valor_sem_desconto"],
        "valor_com_desconto": calc["valor_com_desconto"],
        "saldo_creditos":     calc["saldo_creditos"],
        "ref_mes":            label,
        "status":             "ativo",
    })

    # Recalcula métricas globais com base no mês mais recente
    ativos = [cl for cl in d["clientes"].values() if cl.get("status") == "ativo" and cl.get("ref_mes") == label]
    d["ref_mes"]          = label
    d["atualizado_em"]    = datetime.now().strftime("%d/%m/%Y %H:%M")
    d["faturamento_mes"]  = round(sum(x["valor_com_desconto"] or 0 for x in ativos), 2)
    d["consumo_mes_kwh"]  = sum(x["consumo_faturavel"] or 0 for x in ativos)
    d["acumulado_historico"] = round(d["acumulado_historico"] + calc["valor_com_desconto"], 2)

    hist = d["historico_mensal"]
    ex   = next((h for h in hist if h["mes"] == label), None)
    if ex:
        ex["total"] = d["faturamento_mes"]
    else:
        hist.append({"mes": label, "total": d["faturamento_mes"]})

    salvar(d)

    return {
        "ok": True,
        "cliente": cliente,
        "ref_mes": label,
        "consumo_faturavel": calc["consumo_faturavel"],
        "valor_sem_desconto": calc["valor_sem_desconto"],
        "valor_com_desconto": calc["valor_com_desconto"],
        "saldo_creditos": calc["saldo_creditos"],
        "total_neoenergia": calc["total_neoenergia"],
        "vencimento": calc["vencimento"],
    }

# ── HTML ──────────────────────────────────────────────────────
def html_page(modo: str) -> str:
    is_gestor = modo == "gestor"
    upload_section = """
    <section id="sec-upload">
      <div class="section-title">Carregar fatura Neoenergia</div>
      <div class="upload-card" id="upload-card">
        <div class="upload-top">
          <div>
            <select id="sel-cliente">
              <option value="">Selecione o cliente...</option>
              <option>Real Evolution</option>
              <option>SQS 314</option>
              <option>Oasis Design</option>
              <option>Bello Trigo</option>
              <option>Versato</option>
            </select>
            <label class="file-btn" id="file-label">
              <input type="file" id="file-input" accept=".pdf">
              Escolher PDF
            </label>
            <span id="file-name" class="file-name">Nenhum arquivo</span>
          </div>
          <button id="btn-enviar" onclick="enviarFatura()">Processar fatura</button>
        </div>
        <div id="upload-resultado" class="upload-resultado" style="display:none"></div>
      </div>
    </section>
    """ if is_gestor else ""

    titulo_badge = "Gestor" if is_gestor else "Usina"
    cor_badge    = "#c8860a" if is_gestor else "#2d7a3a"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Patuá Solar</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#f5f5f3;--surf:#fff;--bord:#e4e4e0;--bord-s:#c8c8c2;
  --txt:#1a1a18;--txt3:#9a9a94;
  --sol:#c8860a;--sol-bg:#fef3d8;--sol-bord:#f0c96a;
  --grn:#2d7a3a;--grn-bg:#e8f5eb;
  --amb:#b85c00;--amb-bg:#fff3e0;
  --r:10px;
}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--txt);padding-bottom:48px}}
header{{background:var(--surf);border-bottom:1px solid var(--bord);padding:16px 28px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}}
.logo{{display:flex;align-items:center;gap:10px}}
.logo-ico{{width:30px;height:30px;background:var(--sol);border-radius:8px;
  display:flex;align-items:center;justify-content:center}}
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
.note{{display:inline-block;font-size:10px;color:var(--txt3);background:#f0f0ec;
  border-radius:4px;padding:1px 7px;font-style:italic}}
.dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}}
.dg{{background:var(--grn)}}.da{{background:var(--sol)}}
.tfoot td{{background:#fafaf8;font-weight:700;font-size:13px;
  border-top:2px solid var(--bord-s);border-bottom:none}}

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
.pf{{height:100%;border-radius:2px}}
.pf-ok{{background:#c8d8a8}}.pf-warn{{background:var(--sol)}}

/* UPLOAD */
.upload-card{{background:var(--surf);border:1px solid var(--bord);border-radius:var(--r);padding:18px 20px}}
.upload-top{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.upload-top > div{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
select{{height:36px;border:1px solid var(--bord-s);border-radius:8px;
  padding:0 12px;font-size:13px;color:var(--txt);background:var(--surf);
  outline:none;cursor:pointer;min-width:180px}}
select:focus{{border-color:var(--sol)}}
.file-btn{{display:inline-flex;align-items:center;height:36px;padding:0 14px;
  border:1px solid var(--bord-s);border-radius:8px;font-size:13px;
  color:var(--txt);cursor:pointer;background:var(--surf);white-space:nowrap}}
.file-btn:hover{{background:#f5f5f3;border-color:var(--sol)}}
.file-btn input{{display:none}}
.file-name{{font-size:12px;color:var(--txt3)}}
#btn-enviar{{height:36px;padding:0 20px;background:var(--sol);color:#fff;
  border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap}}
#btn-enviar:hover{{background:#a06a06}}
#btn-enviar:disabled{{background:#ccc;cursor:not-allowed}}
.upload-resultado{{margin-top:14px;padding:14px 16px;border-radius:8px;font-size:13px;line-height:1.6}}
.res-ok{{background:var(--grn-bg);border:1px solid #b8dbbe;color:#1a4a22}}
.res-err{{background:#fdeaea;border:1px solid #f5b8b8;color:#7a1a1a}}
.res-row{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(0,0,0,.06)}}
.res-row:last-child{{border-bottom:none}}
.res-label{{color:inherit;opacity:.75}}
.res-val{{font-weight:600}}

.footer{{text-align:center;font-size:11px;color:var(--txt3);margin-top:32px;
  padding-top:18px;border-top:1px solid var(--bord)}}
</style>
</head>
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
  {'<!-- upload apenas para gestor -->' + upload_section if is_gestor else ''}

  <div class="metrics">
    <div class="mc hi"><div class="mc-label">Faturamento do mês</div><div class="mc-val" id="m-fat">—</div><div class="mc-sub" id="m-fat-sub">—</div></div>
    <div class="mc"><div class="mc-label">Consumo compensado</div><div class="mc-val" id="m-kwh">—</div><div class="mc-sub">kWh no mês</div></div>
    <div class="mc"><div class="mc-label">Acumulado histórico</div><div class="mc-val" id="m-acum">—</div><div class="mc-sub">Total faturado desde o início</div></div>
  </div>

  <section>
    <div class="section-title">Clientes — posição do mês</div>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Cliente</th>
          <th class="r">Consumo (kWh)</th>
          <th class="r">Tarifa Mtec</th>
          <th class="r">Valor sem desconto</th>
          <th class="r">Valor com desconto</th>
          <th class="r">Saldo créditos</th>
          <th>Contrato</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
        <tfoot><tr class="tfoot">
          <td>Total</td>
          <td class="r" id="t-kwh">—</td>
          <td class="r">—</td>
          <td class="r" id="t-sem">—</td>
          <td class="r" id="t-com">—</td>
          <td class="r" id="t-sal">—</td>
          <td>—</td>
        </tr></tfoot>
      </table>
    </div>
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
const CFG = {json.dumps({k: {"cod": v["cod"], "end": v["end"], "tarifa_mtec": v["tarifa_mtec"], "fim": v["fim"], "prog": v["prog"]} for k,v in CLIENTES_CONFIG.items()}, ensure_ascii=False)};
const ORDEM = {json.dumps(ORDEM)};
const MODO = "{modo}";
const IS_GESTOR = MODO === "gestor";

const BRL = v => v == null ? "—" : "R$\u00a0" + v.toLocaleString("pt-BR",{{minimumFractionDigits:2,maximumFractionDigits:2}});
const KWH = v => v == null ? "—" : v.toLocaleString("pt-BR") + " kWh";
const TAR = v => v == null ? "—" : "R$\u00a0" + v.toFixed(5);

let chart = null;

async function carregar() {{
  const r = await fetch("/api/dados");
  const d = await r.json();

  document.getElementById("ref-mes").textContent = d.ref_mes || "—";
  document.getElementById("atualiz").textContent  = d.atualizado_em ? "Atualizado " + d.atualizado_em : "";
  document.getElementById("m-fat").textContent   = BRL(d.faturamento_mes);
  document.getElementById("m-kwh").textContent   = (d.consumo_mes_kwh||0).toLocaleString("pt-BR");
  document.getElementById("m-acum").textContent  = BRL(d.acumulado_historico);

  const ativos = ORDEM.filter(n => d.clientes[n]?.status === "ativo");
  document.getElementById("m-fat-sub").textContent = ativos.length + " clientes faturados no mês";

  let tKwh=0, tSem=0, tCom=0, tSal=0;
  let tbody = "";
  for (const nome of ORDEM) {{
    const c  = d.clientes[nome];
    const cf = CFG[nome];
    if (!c || !cf) continue;
    const pend = c.status === "aguardando";
    tKwh += c.consumo_faturavel || 0;
    tSem += c.valor_sem_desconto || 0;
    tCom += c.valor_com_desconto || 0;
    tSal += c.saldo_creditos || 0;
    tbody += `<tr>
      <td><div class="cn">${{nome}}</div><div class="cc">Cód. ${{cf.cod}} · ${{cf.end}}</div></td>
      <td class="r">${{pend ? "—" : (c.consumo_faturavel||0).toLocaleString("pt-BR")}}</td>
      <td class="r">${{TAR(cf.tarifa_mtec)}}</td>
      <td class="r">${{pend ? "—" : BRL(c.valor_sem_desconto)}}</td>
      <td class="r">${{pend
        ? '<span class="note">aguardando fatura Neoenergia</span>'
        : '<span class="vd">' + BRL(c.valor_com_desconto) + '</span>'}}</td>
      <td class="r">${{pend ? "—" : KWH(c.saldo_creditos)}}</td>
      <td><span class="dot ${{pend?'da':'dg'}}"></span>${{pend?"Aguardando":"Ativo"}} · ${{cf.fim}}</td>
    </tr>`;
  }}
  document.getElementById("tbody").innerHTML = tbody;
  document.getElementById("t-kwh").textContent = tKwh.toLocaleString("pt-BR") + " kWh";
  document.getElementById("t-sem").textContent = BRL(tSem);
  document.getElementById("t-com").textContent = BRL(tCom);
  document.getElementById("t-sal").textContent = KWH(tSal);

  // Contratos
  let chtml = "";
  for (const nome of ORDEM) {{
    const cf = CFG[nome];
    const warn = cf.prog >= 85;
    chtml += `<div class="cc2${{warn?' alert':''}}">
      <div class="ct">
        <span class="ct-name">${{nome}}</span>
        <span class="ct-date${{warn?' warn':''}}">${{cf.fim}}</span>
      </div>
      <div class="pb"><div class="pf ${{warn?'pf-warn':'pf-ok'}}" style="width:${{cf.prog}}%"></div></div>
    </div>`;
  }}
  document.getElementById("contratos").innerHTML = chtml;

  // Gráfico
  const hist   = d.historico_mensal || [];
  const labels = hist.map(h => h.mes);
  const vals   = hist.map(h => h.total);
  const cores  = vals.map((_,i) => i === vals.length-1 ? "#c8860a" : "#e8e8e4");
  const bords  = vals.map((_,i) => i === vals.length-1 ? "#a06a06" : "#d4d4ce");
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("chart").getContext("2d"), {{
    type:"bar",
    data:{{ labels, datasets:[{{ data:vals, backgroundColor:cores, borderColor:bords, borderWidth:1, borderRadius:3 }}] }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{ legend:{{display:false}}, tooltip:{{ callbacks:{{ label: c => BRL(c.parsed.y) }} }} }},
      scales:{{
        x:{{ grid:{{display:false}}, ticks:{{font:{{size:9}},color:"#9a9a94",maxRotation:45}} }},
        y:{{ grid:{{color:"#f0f0ec"}}, border:{{dash:[3,3]}},
          ticks:{{font:{{size:10}},color:"#9a9a94", callback: v => "R$"+(v/1000).toFixed(0)+"k"}} }}
      }}
    }}
  }});

  document.getElementById("footer").textContent =
    "Patuá Solar · Dados da planilha de gestão · " + (d.atualizado_em||"");
}}

{"" if not is_gestor else """
// Upload
document.getElementById("file-input").addEventListener("change", function() {
  const nm = this.files[0]?.name || "Nenhum arquivo";
  document.getElementById("file-name").textContent = nm;
  document.getElementById("file-label").textContent = "PDF selecionado ✓";
});

async function enviarFatura() {
  const cliente = document.getElementById("sel-cliente").value;
  const file    = document.getElementById("file-input").files[0];
  const btn     = document.getElementById("btn-enviar");
  const res     = document.getElementById("upload-resultado");

  if (!cliente) { alert("Selecione um cliente."); return; }
  if (!file)    { alert("Selecione o arquivo PDF."); return; }

  btn.disabled = true;
  btn.textContent = "Processando...";
  res.style.display = "none";

  const form = new FormData();
  form.append("cliente", cliente);
  form.append("fatura", file);

  try {
    const r  = await fetch("/api/upload", { method:"POST", body: form });
    const rj = await r.json();

    if (!r.ok) {
      res.className   = "upload-resultado res-err";
      res.innerHTML   = "<strong>Erro:</strong> " + (rj.detail || "Falha no processamento.");
      res.style.display = "block";
    } else {
      res.className = "upload-resultado res-ok";
      const brl = v => "R$ " + v.toLocaleString("pt-BR",{minimumFractionDigits:2});
      res.innerHTML = `
        <strong>✓ ${cliente} — ${rj.ref_mes} processado com sucesso</strong>
        <div style="margin-top:10px">
          <div class="res-row"><span class="res-label">Consumo faturável</span><span class="res-val">${rj.consumo_faturavel.toLocaleString("pt-BR")} kWh</span></div>
          <div class="res-row"><span class="res-label">Valor sem desconto</span><span class="res-val">${brl(rj.valor_sem_desconto)}</span></div>
          <div class="res-row"><span class="res-label">Valor com desconto</span><span class="res-val">${brl(rj.valor_com_desconto)}</span></div>
          <div class="res-row"><span class="res-label">Saldo de créditos</span><span class="res-val">${rj.saldo_creditos.toLocaleString("pt-BR")} kWh</span></div>
          <div class="res-row"><span class="res-label">Fatura Neoenergia</span><span class="res-val">R$ ${rj.total_neoenergia} · vence ${rj.vencimento}</span></div>
        </div>`;
      res.style.display = "block";
      await carregar();
    }
  } catch(e) {
    res.className   = "upload-resultado res-err";
    res.innerHTML   = "Erro de conexão: " + e.message;
    res.style.display = "block";
  }
  btn.disabled = false;
  btn.textContent = "Processar fatura";
}
"""}

carregar();
setInterval(carregar, 120000);
</script>
</body>
</html>"""

@app.get("/gestor", response_class=HTMLResponse)
def pg_gestor():
    return HTMLResponse(html_page("gestor"))

@app.get("/usina", response_class=HTMLResponse)
def pg_usina():
    return HTMLResponse(html_page("usina"))

@app.get("/")
def root():
    return RedirectResponse("/gestor")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
