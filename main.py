"""
Patuá Solar — Sistema Web Completo v3
  /gestor → dashboard + upload + relatório
  /usina  → somente leitura
Deploy: uvicorn main:app --host 0.0.0.0 --port $PORT
"""
import re, json, os, io
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
import pdfplumber

app = FastAPI()
DADOS_PATH = Path("data/dashboard.json")
DADOS_PATH.parent.mkdir(exist_ok=True)

CLIENTES_CONFIG = {
    "Real Evolution": {"cod":"2972408-2","end":"SQNW 109",        "tarifa_neo":0.97030,"tarifa_mtec":0.77624,"desconto":0.20,"fim":"Jul/27","prog":68},
    "SQS 314":        {"cod":"3079816-7","end":"SQS 314",          "tarifa_neo":0.99926,"tarifa_mtec":0.81939,"desconto":0.18,"fim":"Ago/26","prog":90},
    "Oasis Design":   {"cod":"3079816",  "end":"Águas Claras",     "tarifa_neo":0.95975,"tarifa_mtec":0.76780,"desconto":0.20,"fim":"Mar/27","prog":58},
    "Bello Trigo":    {"cod":"3140795",  "end":"Jardim Botânico",  "tarifa_neo":0.98049,"tarifa_mtec":0.78439,"desconto":0.20,"fim":"Ago/27","prog":42},
    "Versato":        {"cod":"—",        "end":"Brasília-DF",      "tarifa_neo":1.03640,"tarifa_mtec":0.82912,"desconto":0.20,"fim":"Ago/27","prog":42},
}
ORDEM = ["Real Evolution","SQS 314","Oasis Design","Bello Trigo","Versato"]

HISTORICO_ECONOMIA = {
    "Real Evolution":[
        {"mes":"Mai/25","economia":728},{"mes":"Jun/25","economia":987},{"mes":"Jul/25","economia":986},
        {"mes":"Ago/25","economia":987},{"mes":"Set/25","economia":1118},{"mes":"Out/25","economia":870},
        {"mes":"Nov/25","economia":870},{"mes":"Dez/25","economia":870},{"mes":"Jan/26","economia":870},
        {"mes":"Fev/26","economia":869},{"mes":"Mar/26","economia":870},{"mes":"Abr/26","economia":728},
        {"mes":"Mai/26","economia":2779},
    ],
    "Bello Trigo":[
        {"mes":"Ago/25","economia":2085},{"mes":"Set/25","economia":2795},{"mes":"Out/25","economia":2687},
        {"mes":"Nov/25","economia":2672},{"mes":"Dez/25","economia":2801},{"mes":"Jan/26","economia":2914},
        {"mes":"Fev/26","economia":2732},{"mes":"Mar/26","economia":2931},{"mes":"Abr/26","economia":3285},
        {"mes":"Mai/26","economia":3146},
    ],
    "Oasis Design":[
        {"mes":"Mai/25","economia":3824},{"mes":"Jun/25","economia":3591},{"mes":"Jul/25","economia":3670},
        {"mes":"Ago/25","economia":4353},{"mes":"Set/25","economia":4284},{"mes":"Out/25","economia":4101},
        {"mes":"Nov/25","economia":4043},{"mes":"Dez/25","economia":4497},{"mes":"Jan/26","economia":4592},
        {"mes":"Fev/26","economia":4508},{"mes":"Mar/26","economia":4499},{"mes":"Abr/26","economia":4300},
        {"mes":"Mai/26","economia":4008},
    ],
    "Versato":[
        {"mes":"Nov/25","economia":2404},{"mes":"Dez/25","economia":2769},{"mes":"Jan/26","economia":2852},
        {"mes":"Fev/26","economia":2620},{"mes":"Mar/26","economia":3068},{"mes":"Abr/26","economia":2703},
        {"mes":"Mai/26","economia":2305},
    ],
    "SQS 314":[
        {"mes":"Mai/24","economia":566},{"mes":"Jun/24","economia":524},{"mes":"Jul/24","economia":507},
        {"mes":"Ago/24","economia":598},{"mes":"Set/24","economia":571},{"mes":"Out/24","economia":537},
        {"mes":"Nov/24","economia":563},{"mes":"Dez/24","economia":653},{"mes":"Jan/25","economia":641},
    ],
}

ESTADO_INICIAL = {
    "ref_mes":"Mai/26","atualizado_em":"2026-06-27",
    "faturamento_mes":47370.89,"consumo_mes_kwh":60361,"acumulado_historico":567782.57,
    "clientes":{
        "Real Evolution":{"consumo_faturavel":13820,"valor_sem_desconto":13506.58,"valor_com_desconto":10727.64,"saldo_creditos":109513,"ref_mes":"Mai/26","status":"ativo","creditos_utilizados":13920,"tarifa_neo":0.97030,"data_relatorio":None},
        "SQS 314":       {"consumo_faturavel":None,"valor_sem_desconto":None,"valor_com_desconto":None,"saldo_creditos":None,"ref_mes":None,"status":"aguardando","creditos_utilizados":None,"tarifa_neo":0.99926,"data_relatorio":None},
        "Oasis Design":  {"consumo_faturavel":20380,"valor_sem_desconto":19655.68,"valor_com_desconto":15647.76,"saldo_creditos":69713,"ref_mes":"Mai/26","status":"ativo","creditos_utilizados":20480,"tarifa_neo":0.95975,"data_relatorio":None},
        "Bello Trigo":   {"consumo_faturavel":15541,"valor_sem_desconto":15335.84,"valor_com_desconto":12190.24,"saldo_creditos":26677,"ref_mes":"Mai/26","status":"ativo","creditos_utilizados":15641,"tarifa_neo":0.98049,"data_relatorio":None},
        "Versato":       {"consumo_faturavel":10620,"valor_sem_desconto":11110.21,"valor_com_desconto":8805.25,"saldo_creditos":68964,"ref_mes":"Mai/26","status":"ativo","creditos_utilizados":10720,"tarifa_neo":1.03640,"data_relatorio":None},
    },
    "historico_mensal":[
        {"mes":"Mai/24","total":2122},{"mes":"Jun/24","total":1934},{"mes":"Jul/24","total":1860},
        {"mes":"Ago/24","total":2270},{"mes":"Set/24","total":2147},{"mes":"Out/24","total":1991},
        {"mes":"Nov/24","total":2106},{"mes":"Dez/24","total":14410},{"mes":"Jan/25","total":12671},
        {"mes":"Fev/25","total":13703},{"mes":"Mar/25","total":12607},{"mes":"Abr/25","total":2171},
        {"mes":"Mai/25","total":28178},{"mes":"Jun/25","total":27003},{"mes":"Jul/25","total":24279},
        {"mes":"Ago/25","total":34945},{"mes":"Set/25","total":39510},{"mes":"Out/25","total":34339},
        {"mes":"Nov/25","total":44092},{"mes":"Dez/25","total":48342},{"mes":"Jan/26","total":51093},
        {"mes":"Fev/26","total":47272},{"mes":"Mar/26","total":52400},{"mes":"Abr/26","total":47922},
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
    # Normaliza quebras de palavras comuns nas faturas Neoenergia
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

    # Código do cliente — tenta múltiplos padrões de endereço
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
    d   = carregar()
    c   = d["clientes"].get(cliente)
    cfg = CLIENTES_CONFIG.get(cliente)
    if not c or not cfg or c.get("status") == "aguardando":
        raise ValueError("Cliente sem dados processados para gerar relatório.")

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

    cfg   = CLIENTES_CONFIG[cliente]
    calc  = calcular(dados_pdf, cfg)
    label = ref_label(calc["ref_mes"])

    # ── Bloqueio de duplicata ─────────────────────────────────
    d = carregar()
    c = d["clientes"][cliente]
    if c.get("ref_mes") == label and c.get("data_relatorio"):
        raise HTTPException(409, f"Já existe um relatório emitido para {cliente} em {label} ({c['data_relatorio']}). Para reprocessar, cancele o relatório existente primeiro.")

    c.update({
        "consumo_faturavel":   calc["consumo_faturavel"],
        "valor_sem_desconto":  calc["valor_sem_desconto"],
        "valor_com_desconto":  calc["valor_com_desconto"],
        "saldo_creditos":      calc["saldo_creditos"],
        "creditos_utilizados": dados_pdf["creditos_utilizados"],
        "tarifa_neo":          cfg["tarifa_neo"],
        "ref_mes":             label,
        "status":              "ativo",
        "data_fatura":         datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_relatorio":      None,  # reset ao carregar nova fatura
    })

    ativos = [cl for cl in d["clientes"].values() if cl.get("status") == "ativo" and cl.get("ref_mes") == label]
    d["ref_mes"]             = label
    d["atualizado_em"]       = datetime.now().strftime("%d/%m/%Y %H:%M")
    d["faturamento_mes"]     = round(sum(x["valor_com_desconto"] or 0 for x in ativos), 2)
    d["consumo_mes_kwh"]     = sum(x["consumo_faturavel"] or 0 for x in ativos)
    d["acumulado_historico"] = round(d["acumulado_historico"] + calc["valor_com_desconto"], 2)

    hist = d["historico_mensal"]
    ex   = next((h for h in hist if h["mes"] == label), None)
    if ex:
        ex["total"] = d["faturamento_mes"]
    else:
        hist.append({"mes": label, "total": d["faturamento_mes"]})

    salvar(d)
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

    # ── Bloqueio de duplicata ─────────────────────────────────
    d = carregar()
    c = d["clientes"].get(cliente, {})
    if c.get("data_relatorio"):
        raise HTTPException(409, f"Relatório de {c['ref_mes']} já emitido em {c['data_relatorio']}.")

    try:
        pdf_bytes = gerar_relatorio_pdf(cliente, observacoes)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar PDF: {e}")

    # Marca relatório como emitido
    c["data_relatorio"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    salvar(d)

    nome_arquivo = f"Relatorio_{cliente.replace(' ','_')}_{datetime.now().strftime('%Y%m')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'}
    )

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
    }
    res.style.display = "block";
  } catch(e) {
    res.className = "upload-resultado res-err";
    res.innerHTML = "Erro de conexão: " + e.message;
    res.style.display = "block";
  }
  btn.disabled = false; btn.textContent = "Baixar relatório PDF";
}
""" if is_gestor else ""

    # Abreviações dos nomes para o card de métricas
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
        <th>Emissão fatura</th>
        <th>Contrato</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
      <tfoot><tr class="tfoot">
        <td>Total</td>
        <td class="r" id="t-com">—</td>
        <td class="r" id="t-kwh">—</td>
        <td class="r">—</td>
        <td class="r" id="t-sal">—</td>
        <td>—</td><td>—</td>
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

  // Card sub: lista abreviada dos clientes faturados no mês
  const ativos=ORDEM.filter(n=>d.clientes[n]?.status==="ativo"&&d.clientes[n]?.ref_mes===d.ref_mes);
  document.getElementById("m-fat-sub").textContent=
    ativos.length ? ativos.map(n=>ABREV[n]||n).join(" · ") : "Nenhum cliente faturado";

  let tCom=0,tKwh=0,tSal=0,tbody="";
  for(const nome of ORDEM){{
    const c=d.clientes[nome],cf=CFG[nome];
    if(!c||!cf)continue;
    const pend=c.status==="aguardando";
    tCom+=c.valor_com_desconto||0;
    tKwh+=c.consumo_faturavel||0;
    tSal+=c.saldo_creditos||0;
    const relTag=c.data_relatorio?`<span class="tag-rel">✓ ${c.data_relatorio}</span>`:"—";
    tbody+=`<tr>
      <td><div class="cn">${{nome}}</div><div class="cc">Cód. ${{cf.cod}} · ${{cf.end}}</div></td>
      <td class="r">${{pend?'<span class="note">aguardando fatura</span>':'<span class="vd">'+BRL(c.valor_com_desconto)+'</span>'}}</td>
      <td class="r">${{pend?"—":(c.consumo_faturavel||0).toLocaleString("pt-BR")}}</td>
      <td class="r">${{TAR(cf.tarifa_mtec)}}</td>
      <td class="r">${{pend?"—":KWH(c.saldo_creditos)}}</td>
      <td>${{pend?"—":relTag}}</td>
      <td><span class="dot ${{pend?'da':'dg'}}"></span>${{pend?"Aguardando":"Ativo"}} · ${{cf.fim}}</td>
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
      <span class="ct-date${{warn?' warn':''}}">${{cf.fim}}</span></div>
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
