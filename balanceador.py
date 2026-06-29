import flet as ft
import pg8000.dbapi
import os
import math
import ssl
import certifi
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# --- FUNÇÃO DE CONEXÃO COMPATÍVEL COM ANDROID/DESKTOP ---
def obter_conexao():
    url_banco = os.getenv("DATABASE_URL")
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
    page.title = "⚖️ Balanceador de Pelada"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 450
    page.window_height = 750
    
    # --- AJUSTES VISUAIS (BORDAS E ESPAÇAMENTOS) ---
    # Descola o app da barra de bateria e hora do celular
    page.padding = ft.padding.only(top=50, left=20, right=20, bottom=20)
    page.spacing = 5 # Junta a linha de atualização ao topo do conteúdo

    # =====================================================================
    # BUSCA A ÚLTIMA DATA DE ATUALIZAÇÃO
    # =====================================================================
    try:
        conn = obter_conexao()
        c = conn.cursor()
        c.execute("SELECT MAX(data) FROM partidas")
        resultado = c.fetchone()
        conn.close()
        
        if resultado and resultado[0]:
            ultima_data_str = resultado[0].strftime("%d/%m/%Y")
        else:
            ultima_data_str = "--/--/----"
    except Exception:
        ultima_data_str = "Indisponível"

    # Adiciona o texto direto no topo da tela, discreto e em uma linha
    page.add(
        ft.Text(
            f"Última atualização: {ultima_data_str}", 
            size=11, 
            color=ft.Colors.GREY_500, 
            italic=True,
            max_lines=1
        )
    )

    # Container dinâmico para alternar entre as telas
    conteudo = ft.Column(expand=True, scroll="adaptive", spacing=20)
    page.add(conteudo)

    # =====================================================================
    # TELA 2: PERFIL DETALHADO (ENTROSAMENTO TOP 10 MAIS/MENOS)
    # =====================================================================
    def abrir_perfil_entrosamento(jogador_nome):
        conteudo.controls.clear()

        # Botão para voltar à lista principal
        btn_voltar = ft.ElevatedButton(
            "⬅️ Voltar ao Ranking de Nível", 
            on_click=lambda e: carregar_lista_balanceamento(),
            color=ft.Colors.WHITE
        )
        conteudo.controls.append(btn_voltar)

        # Cabeçalho do Jogador
        conteudo.controls.append(
            ft.Row([
                ft.Text("📊", size=30),
                ft.Text(jogador_nome, size=24, weight=ft.FontWeight.BOLD)
            ], alignment=ft.MainAxisAlignment.CENTER)
        )

        parceiros_mais = []
        parceiros_menos = []

        try:
            conn = obter_conexao()
            c = conn.cursor()

            query_entrosamento = """
                SELECT 
                    s2.jogador as parceiro, 
                    COUNT(s2.partida_id) as jogos_juntos, 
                    SUM(CASE WHEN s2.time = p.campeao THEN 1 ELSE 0 END) as vitorias_juntas
                FROM stats_jogadores s1
                JOIN stats_jogadores s2 ON s1.partida_id = s2.partida_id AND s1.time = s2.time
                JOIN partidas p ON s1.partida_id = p.id
                WHERE s1.jogador = %s AND s2.jogador != %s
                GROUP BY s2.jogador
            """
            c.execute(query_entrosamento, (jogador_nome, jogador_nome))
            todos_parceiros = c.fetchall()
            conn.close()

            dados_formatados = [[p[0], int(p[1]), int(p[2])] for p in todos_parceiros]

            # 1. TOP 10 MAIS JOGOU JUNTO
            dados_formatados.sort(key=lambda x: x[1], reverse=True)
            parceiros_mais = dados_formatados[:10]

            # 2. TOP 10 MENOS JOGOU JUNTO
            dados_formatados.sort(key=lambda x: x[1], reverse=False)
            parceiros_menos = dados_formatados[:10]

        except Exception as erro:
            conteudo.controls.append(ft.Text(f"Erro ao carregar dados: {erro}", color=ft.Colors.RED_400))
            page.update()
            return

        # --- TABELA 1: MAIS JOGOU JUNTO ---
        conteudo.controls.append(ft.Text("🤝 Top 10 - Mais Jogou Junto", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_300))
        tabela_mais = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Parceiro")),
                ft.DataColumn(ft.Text("Jogos"), numeric=True),
                ft.DataColumn(ft.Text("Títulos"), numeric=True),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(p[0])),
                    ft.DataCell(ft.Text(str(p[1]))),
                    ft.DataCell(ft.Text(f"{p[2]} 🏆", color=ft.Colors.AMBER_400 if p[2] > 0 else ft.Colors.GREY_400))
                ]) for p in parceiros_mais
            ]
        )
        conteudo.controls.append(tabela_mais)

        conteudo.controls.append(ft.Divider(height=10))

        # --- TABELA 2: MENOS JOGOU JUNTO ---
        conteudo.controls.append(ft.Text("🔍 Top 10 - Menos Jogou Junto", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_300))
        tabela_menos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Parceiro")),
                ft.DataColumn(ft.Text("Jogos"), numeric=True),
                ft.DataColumn(ft.Text("Títulos"), numeric=True),
            ],
            rows=[
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(p[0])),
                    ft.DataCell(ft.Text(str(p[1]))),
                    ft.DataCell(ft.Text(f"{p[2]} 🏆", color=ft.Colors.AMBER_400 if p[2] > 0 else ft.Colors.GREY_400))
                ]) for p in parceiros_menos
            ]
        )
        conteudo.controls.append(tabela_menos)
        
        page.update()

    # =====================================================================
    # TELA 1: LISTA PRINCIPAL DE BALANCEAMENTO
    # =====================================================================
    def carregar_lista_balanceamento():
        conteudo.controls.clear()

        conteudo.controls.append(
            ft.Row([
                ft.Text("⚖️ Nível de Habilidade", size=24, weight=ft.FontWeight.BOLD)
            ], alignment=ft.MainAxisAlignment.CENTER)
        )
        conteudo.controls.append(
            ft.Text(
                "Nível dos jogadores || Fórmula= (Títulos*3 + Gols*2 + Assist*1) / Jogos", 
                size=12, color=ft.Colors.GREY_500, italic=True
            )
        )

        tabela_niveis = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Pos")),
                ft.DataColumn(ft.Text("Jogador (Clique)")),
                ft.DataColumn(ft.Text("Nível"), numeric=True),
            ],
            rows=[]
        )

        try:
            conn = obter_conexao()
            c = conn.cursor()
            
            query_calculo = """
                SELECT 
                    s.jogador,
                    COUNT(s.partida_id) as jogos,
                    SUM(s.gols) as gols,
                    SUM(s.assistencias) as assistencias,
                    SUM(CASE WHEN s.time = p.campeao THEN 1 ELSE 0 END) as titulos
                FROM stats_jogadores s
                JOIN partidas p ON s.partida_id = p.id
                GROUP BY s.jogador
            """
            c.execute(query_calculo)
            dados_brutos = c.fetchall()
            conn.close()

            lista_jogadores_nivel = []

            for generator in dados_brutos:
                nome = generator[0]
                jogos = int(generator[1]) if generator[1] else 0
                gols = int(generator[2]) if generator[2] else 0
                assistencias = int(generator[3]) if generator[3] else 0
                titulos = int(generator[4]) if generator[4] else 0

                if jogos > 0:
                    nivel = ((titulos * 3) + (gols * 2) + (assistencias * 1)) / jogos
                else:
                    nivel = 0.0

                lista_jogadores_nivel.append({"nome": nome, "nivel": nivel})

            lista_jogadores_nivel.sort(key=lambda x: x["nivel"], reverse=True)

            for i, jogador in enumerate(lista_jogadores_nivel):
                posicao = i + 1
                nome_atleta = jogador["nome"]
                valor_nivel = jogador["nivel"]

                botao_jogador = ft.TextButton(
                    nome_atleta,
                    on_click=lambda e, n=nome_atleta: abrir_perfil_entrosamento(n),
                    style=ft.ButtonStyle(color=ft.Colors.BLUE_300)
                )

                tabela_niveis.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(f"{posicao}º")),
                        ft.DataCell(botao_jogador),
                        ft.DataCell(ft.Text(f"{valor_nivel:.2f}", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400))
                    ])
                )

            conteudo.controls.append(tabela_niveis)

        except Exception as erro:
            conteudo.controls.append(ft.Text(f"Erro ao carregar banco: {erro}", color=ft.Colors.RED_400))

        page.update()

    carregar_lista_balanceamento()

ft.app(target=main)