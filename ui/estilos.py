"""Paleta e estilos reutilizáveis da interface."""

FUNDO_PRINCIPAL = "#111827"
FUNDO_PAINEL = "#1F2937"
FUNDO_SECUNDARIO = "#374151"
AZUL = "#2563EB"
AZUL_CLARO = "#60A5FA"
VERDE = "#10B981"
TEXTO = "#F9FAFB"
TEXTO_SECUNDARIO = "#9CA3AF"
AMARELO = "#F59E0B"


ESTILO_APLICACAO = f"""
QMainWindow, QWidget#raiz {{
    background-color: {FUNDO_PRINCIPAL};
    color: {TEXTO};
    font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
}}
QFrame#barraSuperior {{
    background-color: #182235;
    border-bottom: 1px solid #2D3A4F;
}}
QMenuBar#menuProjeto {{
    background-color: #111827;
    color: {TEXTO_SECUNDARIO};
    border-bottom: 1px solid #2D3A4F;
    padding-left: 12px;
}}
QMenuBar#menuProjeto::item {{
    background: transparent;
    padding: 5px 10px;
}}
QMenuBar#menuProjeto::item:selected, QMenu {{
    background-color: #1F2937;
    color: {TEXTO};
}}
QMenu::item {{
    padding: 7px 24px 7px 12px;
}}
QMenu::item:selected {{ background-color: {AZUL}; }}
QLabel#marca {{
    min-width: 38px;
    min-height: 38px;
    max-width: 38px;
    max-height: 38px;
    border-radius: 10px;
    background-color: {AZUL};
    color: white;
    font-size: 13px;
    font-weight: 800;
}}
QLabel#tituloAplicacao {{
    color: {TEXTO};
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 1px;
}}
QLabel#subtituloAplicacao, QLabel#textoSecundario {{
    color: {TEXTO_SECUNDARIO};
    font-size: 11px;
}}
QLabel#cenario {{
    color: #BFDBFE;
    background-color: #1E3A5F;
    border: 1px solid #28558A;
    border-radius: 12px;
    padding: 6px 12px;
}}
QFrame#painel, QFrame#painelResultados, QFrame#areaVisualizacao {{
    background-color: {FUNDO_PAINEL};
    border: 1px solid #2D3A4F;
    border-radius: 12px;
}}
QWidget#cidade3D {{
    background-color: #0B1220;
    border: 1px solid #2D3A4F;
    border-radius: 8px;
}}
QWidget#controlesCidade3D {{
    background-color: #182235;
    border-top: 1px solid #344258;
}}
QPushButton#botao3D {{
    min-height: 27px;
    padding: 0 8px;
    font-size: 11px;
}}
QProgressBar#progressoCidade3D {{
    min-height: 14px;
    border: 1px solid #344258;
    border-radius: 6px;
    background-color: #111827;
    color: #E5E7EB;
    text-align: center;
}}
QProgressBar#progressoCidade3D::chunk {{
    background-color: #10B981;
    border-radius: 5px;
}}
QLabel#estadoCidade3D {{
    color: #CBD5E1;
    font-size: 11px;
}}
QFrame#painelPassos {{
    background-color: #182235;
    border: 1px solid #344258;
    border-radius: 9px;
}}
QLabel#descricaoPasso {{
    color: #DCE3EC;
    background-color: #111827;
    border: 1px solid #344258;
    border-radius: 6px;
    padding: 6px;
}}
QPushButton#botaoPasso {{
    min-height: 27px;
    padding: 0 7px;
    font-size: 11px;
}}
QFrame#cartaoResultado {{
    background-color: #182235;
    border: 1px solid #344258;
    border-radius: 8px;
}}
QFrame#cartaoResultado QLabel {{
    color: #DCE3EC;
    background-color: transparent;
    border: none;
}}
QLabel#tituloPainel {{
    color: {TEXTO_SECUNDARIO};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#tituloVisualizacao {{
    color: {TEXTO};
    font-size: 15px;
    font-weight: 700;
}}
QPushButton {{
    background-color: {FUNDO_SECUNDARIO};
    color: {TEXTO};
    border: 1px solid #4B5563;
    border-radius: 8px;
    min-height: 34px;
    padding: 0 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #46556A;
    border-color: #64748B;
}}
QPushButton:pressed {{ background-color: #273449; }}
QPushButton:checked {{
    background-color: {AZUL};
    border-color: {AZUL_CLARO};
    color: white;
}}
QPushButton#botaoPrimario {{
    background-color: {AZUL};
    border-color: {AZUL_CLARO};
}}
QPushButton#botaoPrimario:hover {{ background-color: #3474DD; }}
QPushButton#botaoMissao3D {{
    background-color: #B45309;
    border-color: #F59E0B;
    color: #FFFBEB;
}}
QPushButton#botaoMissao3D:hover {{ background-color: #D97706; }}
QPushButton#botaoFerramenta {{
    text-align: left;
    padding-left: 12px;
}}
QPushButton:disabled {{
    background-color: #242F40;
    color: #697586;
    border-color: #303C4E;
}}
QListWidget, QComboBox {{
    background-color: #182235;
    color: {TEXTO};
    border: 1px solid #344258;
    border-radius: 8px;
    padding: 5px;
    outline: none;
}}
QListWidget::item {{
    min-height: 30px;
    border-radius: 6px;
    padding-left: 6px;
}}
QListWidget::item:hover {{ background-color: #2B3A50; }}
QListWidget::item:selected {{
    background-color: #1D4ED8;
    color: white;
}}
QListWidget:disabled, QComboBox:disabled {{
    background-color: #18202D;
    color: #667085;
    border-color: #2C3748;
}}
QLabel#detalhesLocal {{
    background-color: #182235;
    color: #D1D5DB;
    border: 1px solid #344258;
    border-radius: 8px;
    padding: 10px;
}}
QLabel#aviso {{
    background-color: #3A3020;
    color: #FCD68A;
    border: 1px solid #6B5223;
    border-radius: 8px;
    padding: 10px;
}}
QLabel#estadoVazio {{
    color: {TEXTO_SECUNDARIO};
    font-style: italic;
}}
QGraphicsView {{
    border: none;
    border-radius: 8px;
    background-color: #121B29;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: 7px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: #475569;
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QSplitter::handle {{ background-color: transparent; width: 8px; }}
QToolTip {{
    background-color: #0F172A;
    color: {TEXTO};
    border: 1px solid #475569;
    padding: 6px;
}}
"""
