import flet as ft
import pg8000.dbapi
import math
import ssl
import certifi
from urllib.parse import urlparse

# --- FUNÇÃO DE CONEXÃO DIRETA (IMUNE A ERROS NO CELULAR) ---
def obter_conexao():
    # ⚠️ ATENÇÃO: Cole o seu link verdadeiro do Neon aqui dentro das aspas!
    url_banco = "postgresql://neondb_owner:npg_RTuJHXq97Oph@ep-dawn-heart-acwd28pq-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    
    url_fatiada = urlparse(url_banco)
    contexto_ssl = ssl.create_default_context(cafile=certifi.where())
    
    return pg8000.dbapi.connect(
        user=url_fatiada.username,
        password=url_fatiada.password,
        host=url_fatiada.hostname,
        port=url_fatiada.port or 5432,
        database=url_fatiada.path.lstrip('/'),
        ssl_context=contexto_ssl
    )

# --- APP PRINCIPAL ---
def main(page: ft.Page):
    page.title = "⚖️ Separador de Times Equilibrados"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 450
    page.window_height = 800
    
    # Ajustes de borda para não colar na barra de notificações do celular
    page.padding = ft.padding.only(top=50, left=20, right=20, bottom=20)
    page.spacing = 5

    # Memória da sessão do aplicativo
    banco_jogadores = {}  # { "Nome": nivel_calculado }
    lista_nomes = []      # Lista apenas com os nomes para o autocompletar
    lista_presentes = []  # Lista dos jogadores adicionados para o sorteio do dia

    # =====================================================================
    # CARREGAMENTO INICIAL (ÚLTIMA DATA E NÍVEIS DO BANCO)
    # =====================================================================
    try:
        conn = obter_conexao()
        c = conn.cursor()
        
        # 1. Busca a última data de atualização
        c.execute("SELECT MAX(data) FROM partidas")
        resultado_data = c.fetchone()
        ultima_data_str = resultado_data[0].strftime("%d/%m/%Y") if resultado_data and resultado_data[0] else "--/--/----"
        
        # 2. Busca dados brutos para calcular o nível de todo mundo
        c.execute("""
            SELECT s.jogador, COUNT(s.partida_id), SUM(s.gols), SUM(s.assistencias),
                   SUM(CASE WHEN s.time = p.campeao THEN 1 ELSE 0 END)
            FROM stats_jogadores s 
            JOIN partidas p ON s.partida_id = p.id 
            GROUP BY s.jogador
        """)
        dados_brutos = c.fetchall()
        conn.close()

        # Calcula o nível usando seus pesos: Titulo*3, Gols*2, Assistencia*1
        for linha in dados_brutos:
            nome_j = linha[0]
            jogos = int(linha[1]) if linha[1] else 0
            gols = int(linha[2]) if linha[2] else 0
            assistencias = int(linha[3]) if linha[3] else 0
            titulos = int(linha[4]) if linha[4] else 0

            if jogos > 0:
                nivel = ((titulos * 3) + (gols * 2) + (assistencias * 1)) / jogos
            else:
                nivel = 0.0
            
            banco_jogadores[nome_j] = nivel
        
        lista_nomes = list(banco_jogadores.keys())

    except Exception:
        ultima_data_str = "Indisponível (Sem Conexão)"

    # --- TEXTO DA ÚLTIMA ATUALIZAÇÃO ---
    page.add(
        ft.Text(f"Última atualização: {ultima_data_str}", size=11, color=ft.Colors.GREY_500, italic=True, max_lines=1)
    )

    # Conteúdo principal com scroll adaptativo
    conteudo = ft.Column(expand=True, scroll="adaptive", spacing=15)
    page.add(conteudo)

    conteudo.controls.append(
        ft.Row([ft.Text("⚖️ Balanceamento dos Times", size=24, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER)
    )

    # =====================================================================
    # CONTROLADORES DE AUTOCOMPLETAR E SELEÇÃO
    # =====================================================================
    def selecionar_sugestao(nome_escolhido):
        txt_nome.value = nome_escolhido
        row_sugestoes.controls.clear()
        page.update()

    def filtrar_nomes(e):
        texto = txt_nome.value.lower().strip()
        row_sugestoes.controls.clear()
        if texto:
            # Filtra os nomes do banco que contêm o texto digitado
            correspondencias = [n for n in lista_nomes if texto in n.lower()]
            for match in correspondencias[:3]:  # Mostra no máximo 3 sugestões para não poluir
                row_sugestoes.controls.append(
                    ft.TextButton(
                        content=ft.Text(match),
                        style=ft.ButtonStyle(color=ft.Colors.BLUE_300),
                        on_click=lambda e, name=match: selecionar_sugestao(name)
                    )
                )
        page.update()

    # --- CAMPOS DE ENTRADA DA INTERFACE ---
    txt_nome = ft.TextField(label="Nome do Jogador", on_change=filtrar_nomes, expand=True)
    row_sugestoes = ft.Row(spacing=5)
    
    cg_posicao = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="Ataque", label="Ataque (Frente)"),
            ft.Radio(value="Defesa", label="Defesa (Trás)"),
        ], alignment=ft.MainAxisAlignment.CENTER),
        value="Ataque"
    )

    col_lista_jogadores = ft.Column(spacing=5)
    txt_qtd_times = ft.TextField(label="Quantidade de Times", value="3", keyboard_type=ft.KeyboardType.NUMBER, width=180)
    col_resultados = ft.Column(spacing=15)

    # =====================================================================
    # AÇÕES DO PROGRAMA (ADICIONAR, RESETAR, SEPARAR)
    # =====================================================================
    def adicionar_atleta(e):
        nome = txt_nome.value.strip()
        if not nome:
            return
        
        # Puxa o nível real do banco. Se for um convidado novo, começa com nível base 1.0
        nivel = banco_jogadores.get(nome, 1.0)
        posicao = cg_posicao.value

        lista_presentes.append({"nome": nome, "posicao": posicao, "nivel": nivel})
        
        # Limpa os campos para o próximo
        txt_nome.value = ""
        row_sugestoes.controls.clear()
        atualizar_lista_visual()

    def remover_atleta(jogador_dict):
        lista_presentes.remove(jogador_dict)
        atualizar_lista_visual()

    def atualizar_lista_visual():
        col_lista_jogadores.controls.clear()
        if lista_presentes:
            col_lista_jogadores.controls.append(ft.Text(f"🏃‍♂️ Atletas Confirmados ({len(lista_presentes)}):", weight=ft.FontWeight.BOLD, size=14))
        
        for p in lista_presentes:
            cor_pos = ft.Colors.RED_400 if p["posicao"] == "Ataque" else ft.Colors.BLUE_400
            col_lista_jogadores.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(p["nome"], weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text(p["posicao"], color=cor_pos, size=12),
                        ft.Text(f"Nível: {p['nivel']:.2f}", color=ft.Colors.GREEN_400, size=12),
                        ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.GREY_500, icon_size=18, on_click=lambda e, pl=p: remover_atleta(pl))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=5,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.GREY_800))
                )
            )
        page.update()

    def resetar_tudo(e):
        lista_presentes.clear()
        col_lista_jogadores.controls.clear()
        col_resultados.controls.clear()
        txt_nome.value = ""
        row_sugestoes.controls.clear()
        txt_qtd_times.value = "3"
        page.update()

    def executar_separacao(e):
        col_resultados.controls.clear()
        try:
            qtd_times = int(txt_qtd_times.value)
        except ValueError:
            col_resultados.controls.append(ft.Text("⚠️ Insira um número válido de times!", color=ft.Colors.RED_400))
            page.update()
            return

        if len(lista_presentes) < qtd_times:
            col_resultados.controls.append(ft.Text("⚠️ Menos jogadores do que a quantidade de times!", color=ft.Colors.RED_400))
            page.update()
            return

        # 1. Separa por setor e ordena do maior nível para o menor
        ataques = [p for p in lista_presentes if p["posicao"] == "Ataque"]
        defesas = [p for p in lista_presentes if p["posicao"] == "Defesa"]
        
        ataques.sort(key=lambda x: x["nivel"], reverse=True)
        defesas.sort(key=lambda x: x["nivel"], reverse=True)

        # 2. Inicializa a estrutura dos times (Agora rastreando a qtd_total)
        times = [{"jogadores": [], "nivel_total": 0.0, "qtd_ataque": 0, "qtd_defesa": 0, "qtd_total": 0} for _ in range(qtd_times)]

        # 3. Distribui os atacantes 
        # Prioridade 1: Menor Tamanho Total (Garante times com mesmo número de pessoas)
        # Prioridade 2: Menos atacantes (Garante divisão tática)
        # Prioridade 3: Menor Nível (Equilibra a força)
        for p in ataques:
            times.sort(key=lambda t: (t["qtd_total"], t["qtd_ataque"], t["nivel_total"]))
            times[0]["jogadores"].append(p)
            times[0]["nivel_total"] += p["nivel"]
            times[0]["qtd_ataque"] += 1
            times[0]["qtd_total"] += 1

        # 4. Distribui os defensores usando a mesma lógica rigorosa de tamanho
        for p in defesas:
            times.sort(key=lambda t: (t["qtd_total"], t["qtd_defesa"], t["nivel_total"]))
            times[0]["jogadores"].append(p)
            times[0]["nivel_total"] += p["nivel"]
            times[0]["qtd_defesa"] += 1
            times[0]["qtd_total"] += 1

        # --- MONTA O VISUAL DOS TIMES SORTEADOS ---
        for i, t in enumerate(times):
            rows_atletas = []
            for jog in t["jogadores"]:
                c_pos = ft.Colors.RED_300 if jog["posicao"] == "Ataque" else ft.Colors.BLUE_300
                rows_atletas.append(
                    ft.Row([
                        ft.Text(jog["nome"], expand=True),
                        ft.Text(jog["posicao"], color=c_pos, size=12),
                        ft.Text(f"{jog['nivel']:.2f}", color=ft.Colors.GREEN_400, size=12)
                    ])
                )

            col_resultados.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"📋 TIME {i+1} ({t['qtd_total']} Jogs)", weight=ft.FontWeight.BOLD, size=16),
                            ft.Text(f"Força Total: {t['nivel_total']:.2f}", color=ft.Colors.AMBER_400, weight=ft.FontWeight.BOLD, size=13)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=5, color=ft.Colors.GREY_700),
                        ft.Column(controls=rows_atletas, spacing=5)
                    ]),
                    padding=15,
                    border=ft.border.all(1, ft.Colors.GREY_800),
                    border_radius=10,
                    bgcolor=ft.Colors.GREY_900
                )
            )
        page.update()

    # =====================================================================
    # MONTAGEM DA ÁRVORE VISUAL DO FORMULÁRIO
    # =====================================================================
    conteudo.controls.append(
        ft.Column([
            ft.Row([txt_nome, ft.ElevatedButton("Adicionar", on_click=adicionar_atleta, color=ft.Colors.WHITE)]),
            row_sugestoes,
            cg_posicao,
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            col_lista_jogadores,
            ft.Divider(height=15),
            ft.Row([txt_qtd_times], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            ft.Row([
                ft.ElevatedButton("🔄 Resetar Tudo", on_click=resetar_tudo, bgcolor=ft.Colors.GREY_800, color=ft.Colors.WHITE),
                ft.ElevatedButton("⚖️ Separar Times", on_click=executar_separacao, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, expand=True),
            ], spacing=10),
            ft.Divider(height=15),
            col_resultados
        ], spacing=10)
    )
    page.update()

import os

# Pega a porta que o servidor nuvem liberar, ou usa 8000 se estiver testando no PC
porta = int(os.getenv("PORT", 8000))

# Avisa o Flet para rodar como site web
ft.app(target=main, view=ft.WEB_BROWSER, host="0.0.0.0", port=porta)