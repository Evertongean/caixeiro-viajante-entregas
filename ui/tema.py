"""Paleta e folha de estilos da nova interface."""

CORES = {
    "fundo": "#07101E",
    "painel": "#0C1829",
    "cartao": "#101F33",
    "borda": "#203651",
    "azul": "#2388FF",
    "azul_hover": "#4BA0FF",
    "laranja": "#F59E0B",
    "texto": "#F4F8FF",
    "texto_secundario": "#91A4BC",
    "sucesso": "#2DD4BF",
}


FOLHA_ESTILOS = """
QMainWindow, QWidget#raizAplicacao {
    background: #07101E;
    color: #F4F8FF;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}
QFrame#cabecalho {
    background: #0A1626;
    border-bottom: 1px solid #1C314B;
}
QLabel#marca {
    background: #2388FF;
    color: white;
    border-radius: 11px;
    font-size: 16px;
    font-weight: 800;
}
QLabel#tituloAplicacao {
    font-size: 20px;
    font-weight: 700;
    color: #F8FBFF;
}
QLabel#subtituloAplicacao, QLabel#textoSecundario, QLabel#notaFutura {
    color: #8498B2;
}
QLabel#instrucaoEditor {
    color: #C5D8EE;
    background: #0A1727;
    border: 1px solid #29445F;
    border-radius: 8px;
    padding: 9px;
}
QLabel#estadoFerramenta {
    color: #99F6E4;
    background: #0B2B32;
    border: 1px solid #1D665F;
    border-radius: 7px;
    padding: 6px 8px;
    font-weight: 700;
}
QLabel#resumoEditor {
    color: #A9BDD4;
    font-size: 11px;
    padding: 2px 3px;
}
QLabel#seloAplicacao {
    color: #78B9FF;
    background: #102A47;
    border: 1px solid #204C76;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 700;
}
QFrame#painelCena, QFrame#painelLateral, QFrame#cartaoInformacao {
    background: #0C1829;
    border: 1px solid #203651;
    border-radius: 14px;
}
QFrame#barraCena {
    background: #0D1B2D;
    border: none;
    border-bottom: 1px solid #1B324D;
    border-top-left-radius: 13px;
    border-top-right-radius: 13px;
}
QLabel#tituloSecao {
    color: #F4F8FF;
    font-size: 14px;
    font-weight: 700;
}
QLabel#estadoCena {
    color: #9FB5CE;
    background: #11243A;
    border: 1px solid #24415F;
    border-radius: 10px;
    padding: 4px 9px;
    font-size: 11px;
}
QGroupBox {
    color: #F4F8FF;
    font-size: 14px;
    font-weight: 700;
    border: 1px solid #213750;
    border-radius: 12px;
    margin-top: 13px;
    padding: 17px 12px 12px 12px;
    background: #0E1C2E;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #DDEAFF;
}
QPushButton {
    background: #17314F;
    border: 1px solid #285177;
    border-radius: 8px;
    color: #EAF3FF;
    min-height: 34px;
    padding: 0 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: #204568;
    border-color: #3C7EBA;
}
QPushButton:pressed {
    background: #112B45;
}
QPushButton:checked {
    background: #146CC7;
    border: 2px solid #73B7FF;
    color: #FFFFFF;
}
QPushButton:disabled {
    color: #65778D;
    background: #111E2E;
    border-color: #243446;
}
QPushButton#botaoPrimario {
    background: #1678E7;
    border-color: #3494FF;
}
QPushButton#botaoPrimario:hover { background: #2388FF; }
QPushButton#botaoMissao {
    background: #F59E0B;
    border-color: #FFB52D;
    color: #101725;
    font-weight: 800;
}
QPushButton#botaoMissao:disabled {
    background: #5A4220;
    border-color: #70522A;
    color: #A99578;
}
QComboBox, QListWidget, QDoubleSpinBox {
    background: #0A1727;
    color: #EAF3FF;
    border: 1px solid #29445F;
    border-radius: 8px;
    min-height: 34px;
    padding: 0 9px;
    selection-background-color: #2388FF;
}
QCheckBox {
    color: #C5D8EE;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 1px solid #3C6B93;
    border-radius: 4px;
    background: #0A1727;
}
QCheckBox::indicator:checked {
    background: #2388FF;
    border-color: #58A7FF;
}
QCheckBox::indicator:indeterminate {
    background: #F59E0B;
    border-color: #FFB52D;
}
QLabel#depositoTsp, QLabel#quantidadeClientes, QLabel#resultadoRota {
    color: #C5D8EE;
    background: #0A1727;
    border: 1px solid #29445F;
    border-radius: 7px;
    padding: 6px 8px;
}
QComboBox:disabled, QListWidget:disabled, QDoubleSpinBox:disabled {
    color: #687B91;
    background: #101B29;
}
QComboBox::drop-down { border: none; width: 28px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #0A1625;
    width: 8px;
    margin: 2px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #315270;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: transparent; width: 8px; }
QLabel#rotuloCartao {
    color: #7F94AE;
    font-size: 11px;
    font-weight: 700;
}
QLabel#valorCartao {
    color: #F5F9FF;
    font-size: 17px;
    font-weight: 700;
}
QLabel#iconeCartao {
    background: #102D4D;
    color: #58A7FF;
    border-radius: 9px;
    font-size: 15px;
    font-weight: 700;
}
QToolTip {
    background: #13263B;
    color: #EAF3FF;
    border: 1px solid #355879;
    padding: 5px;
}
"""


__all__ = ["CORES", "FOLHA_ESTILOS"]
