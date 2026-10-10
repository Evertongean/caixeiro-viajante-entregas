# Delivery Route — Simulador de otimização de rotas

Projeto acadêmico em Python para representar uma rede de entregas como grafo
não direcionado e ponderado, estudar Dijkstra e o Problema do Caixeiro
Viajante (TSP) e visualizar o cenário em uma aplicação desktop 3D.

A nova interface foi reconstruída do zero. Ela apresenta os modelos fornecidos
em `assets/models/cidade.glb` e `assets/models/carro.glb`, navegação de câmera,
controles preparados para as próximas etapas e cartões de estado neutros. O
editor de ruas, o cálculo visual de rotas e a missão animada ainda não fazem
parte desta entrega.

## Requisitos

- Python 3.10 ou mais recente;
- PySide6 6.8 ou mais recente, instalado por `requirements.txt`;
- backend gráfico Qt compatível com OpenGL, Vulkan, Metal ou Direct3D para a
  renderização 3D real.

Instalação recomendada:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Executar

Interface desktop:

```bash
python3 gui_main.py
```

Demonstração textual dos algoritmos:

```bash
python3 main.py
```

## Estrutura

```text
.
├── algorithms/
│   ├── dijkstra.py
│   └── caixeiro_viajante.py
├── models/
│   ├── grafo.py
│   └── persistencia.py
├── ui/
│   ├── assets_3d.py          # valida GLB e gerencia o cache Balsam
│   ├── camera_orbital.py     # estado matemático da câmera
│   ├── cena_3d.qml           # cena Qt Quick 3D única
│   ├── janela_principal.py   # layout e controles
│   ├── tema.py               # paleta azul-marinho e estilos
│   └── visualizacao_3d.py    # ponte QWidget/Qt Quick 3D
├── tests/
├── assets/models/
│   ├── cidade.glb
│   └── carro.glb
├── gui_main.py
└── main.py
```

## Interface

A janela possui três regiões:

- cidade 3D ocupando aproximadamente 75% da área horizontal;
- painel de controles rolável à direita;
- quatro cartões inferiores para distância, percurso, clientes e status.

Os controles da câmera e do enquadramento são funcionais. Ações que pertencem
às próximas entregas aparecem explicitamente desabilitadas e identificadas
como “Em breve”; nenhum botão simula uma operação inexistente.

### Câmera

- botão esquerdo + arrastar: órbita;
- botão direito + arrastar: deslocamento do alvo;
- roda do mouse: zoom com limites;
- **Enquadrar**: restaura a vista calculada pela caixa real da cidade;
- **Visão aérea**: muda somente a câmera;
- **Focar carro**: enquadra o veículo;
- **Câmera livre** e **Atrás do carro**: alternam a estrutura preparada para a
  futura missão.

Nenhuma operação de câmera modifica a geometria dos modelos.

## Carregamento dos GLBs

Qt Quick 3D não usa um GLB diretamente em `Model.source`. Antes de montar a
cena, `ui/assets_3d.py`:

1. valida o cabeçalho glTF 2.0;
2. calcula a caixa do modelo considerando os transforms dos nós;
3. chama o `pyside6-balsam` da mesma instalação do PySide6;
4. armazena QML, malhas e texturas em um cache versionado;
5. reutiliza o resultado enquanto arquivo, data e versão do PySide6 não mudam.

O cache padrão fica em `~/.cache/delivery-route/balsam` no Linux e pode ser
alterado pela variável `DELIVERY_ROUTE_CACHE_DIR`. Os GLBs originais nunca são
modificados. A cena usa `Loader3D`, duas fontes de luz, câmera em perspectiva e
as escalas próprias dos assets existentes.

O carregamento é adiado até a área 3D estar visível e possuir dimensões. A
interface diferencia uma árvore QML corretamente carregada de um backend
gráfico realmente capaz de desenhar Qt Quick 3D, evitando interpretar uma tela
escura como sucesso.

## Núcleo matemático

`models/grafo.py` mantém vértices, arestas, pesos e invariantes do grafo.
`algorithms/dijkstra.py` encontra caminhos mínimos em
`O((V + E) log V)`. `algorithms/caixeiro_viajante.py` avalia exatamente as
permutações dos clientes, com custo fatorial `O(C! · C)` e limite padrão de
oito clientes. As distâncias entre paradas do TSP são obtidas com Dijkstra.

O cenário de demonstração confirma:

- Dijkstra de `D` até `B`: `D → X → A → B`, com 6 km;
- TSP: ordem `D → A → B → C → D` e percurso completo
  `D → X → A → B → C → D`, com 15 km e seis ordens avaliadas.

## Persistência

`models/persistencia.py` salva e carrega somente os dados JSON do grafo:
depósito, vértices, tipos, coordenadas, arestas e pesos. A persistência não é
misturada com câmera, renderização ou cache 3D.

## Testes

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
python3 -m compileall -q algorithms models ui main.py gui_main.py tests
```

A suíte cobre o núcleo matemático, persistência, inspeção dos GLBs, cache de
conversão, câmera orbital, zoom, enquadramento, referências dos modelos,
estados dos controles, inicialização QML, proporção do layout e
redimensionamento.

O backend `offscreen` pode validar a estrutura da cena sem oferecer uma API 3D
real. A confirmação final de materiais, iluminação, enquadramento e fluidez da
navegação deve ser feita executando `gui_main.py` em uma sessão gráfica.
