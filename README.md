# Delivery Route — Simulador de otimização de rotas

Projeto acadêmico em Python para representar uma rede de entregas como grafo
não direcionado e ponderado, estudar Dijkstra e o Problema do Caixeiro
Viajante (TSP) e visualizar o cenário em uma aplicação desktop 3D.

A interface apresenta os modelos fornecidos em `assets/models/cidade.glb` e
`assets/models/carro.glb`, navegação de câmera e um editor que cadastra pontos
e ruas diretamente sobre a geometria 3D. O cálculo visual de rotas e a missão
animada permanecem reservados para as próximas etapas.

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
│   ├── persistencia.py
│   └── projeto_cidade.py     # grafo e metadados espaciais versionados
├── ui/
│   ├── assets_3d.py          # valida GLB e gerencia o cache Balsam
│   ├── camera_orbital.py     # estado matemático da câmera
│   ├── cena_3d.qml           # cena Qt Quick 3D única
│   ├── dialogos_editor.py    # confirmação de pontos, superfícies e pesos
│   ├── editor_cidade.py      # operações espaciais sobre o grafo oficial
│   ├── janela_principal.py   # layout, modos e fluxos do editor
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

Os controles da câmera, do enquadramento e da seção **Editar cidade** são
funcionais. O cálculo visual e a missão aparecem explicitamente desabilitados
como “Em breve”; nenhum botão simula uma operação inexistente.

### Editor visual

O clique é resolvido por `View3D.pick()`. A cena devolve a malha, o material e
`scenePosition`, portanto a posição já considera a hierarquia e a escala do
GLB. O grafo usa o plano `(x, z)` da cena e o projeto conserva também a
coordenada vertical completa `(x, y, z)`.

Os nomes do asset são genéricos e não identificam as ruas com segurança. Por
isso nenhuma malha é considerada trafegável automaticamente:

1. ative **Classificar superfície**;
2. clique no asfalto e marque a malha como **Rua trafegável**;
3. use **Adicionar ponto**, **Adicionar cliente** ou **Definir depósito** e
   clique sobre uma malha já classificada;
4. confira identificador, nome e tipo no diálogo; a posição não é digitada;
5. para uma conexão, ative **Criar rua**, selecione os dois marcadores,
   acrescente curvas clicando no asfalto e confirme o peso oficial.

O botão **Desfazer** remove primeiro a última curva e depois os extremos; o
botão **Cancelar** descarta toda a prévia. Em **Navegar**, marcadores e linhas
podem ser selecionados para edição, reposicionamento ou exclusão. Exclusões
pedem confirmação. Azul identifica o depósito, verde identifica clientes,
cinza identifica cruzamentos e laranja identifica a operação temporária.

Ao confirmar uma rua, o diálogo mostra o comprimento geométrico, o fator
configurável em km/unidade e a sugestão resultante. O peso oficial continua
sendo um campo separado, validado pelo grafo e usado por Dijkstra e TSP.

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

Os botões **Salvar** e **Abrir** usam o formato versionado de
`models/projeto_cidade.py`. Ele armazena o grafo, posições 3D, polilinhas,
classificações manuais, fator de conversão e referências dos GLBs. Os binários
dos modelos não são incorporados ao JSON. Arquivos antigos de
`models/persistencia.py` continuam aceitos; seus vértices sem posição espacial
recebem uma disposição inicial aproximada e podem ser reposicionados sobre
ruas classificadas. O carregamento é transacional: um JSON inválido não
substitui o projeto aberto.

## Testes

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
python3 -m compileall -q algorithms models ui main.py gui_main.py tests
```

A suíte cobre o núcleo matemático, os formatos novo e legado, classificação de
superfícies, criação/edição/exclusão de vértices e ruas, coordenadas, curvas,
pesos, consistência visual, ponte de picking, execução de Dijkstra/TSP após
edições, inspeção dos GLBs, câmera e inicialização QML.

O backend `offscreen` valida a estrutura sem oferecer uma API 3D real. A
validação desta versão também foi executada com OpenGL: cidade e carro foram
materializados e `View3D.pick()` retornou impactos reais com posição, nome da
malha e material. Como a distinção semântica do asset não é confiável, a
classificação rua/calçada/bloqueio continua sendo uma verificação manual
obrigatória do usuário.
