# Delivery Route — Simulador de otimização de rotas

Projeto acadêmico em Python para representar uma rede de entregas como grafo
não direcionado e ponderado, estudar Dijkstra e o Problema do Caixeiro
Viajante (TSP) e visualizar o cenário em uma aplicação desktop 3D.

A interface apresenta os modelos fornecidos em `assets/models/cidade.glb` e
`assets/models/carro.glb`, navegação de câmera e um editor que cadastra pontos
e ruas diretamente sobre a geometria 3D. Dijkstra e TSP podem ser executados
no grafo editado e seus percursos espaciais são destacados na cidade. Uma
missão animada move o carro real pelas polilinhas calibradas, registra entregas
e oferece câmera de perseguição.

Ao abrir a interface, a cidade começa em um estado mínimo: somente o depósito
`D — Depósito Central`, nenhum cliente, nenhuma conexão fictícia e nenhuma
rota. O carro usa uma vaga independente, validada sobre a pista do GLB. A
configuração espacial desse estado fica em
`assets/config/cidade-inicial.json`; o exemplo acadêmico de `main.py` continua
separado e inalterado.

## Requisitos

- Python 3.10 ou mais recente;
- PySide6 6.8 ou mais recente, instalado por `requirements.txt`;
- backend gráfico Qt compatível com OpenGL, Vulkan, Metal ou Direct3D para a
  renderização 3D real.

## Tecnologias

- Python 3, com domínio e algoritmos independentes da interface;
- PySide6/Qt Widgets para a janela e os controles;
- Qt Quick 3D/QML para cena, picking, luzes, marcadores e destaques;
- glTF 2.0/GLB e `pyside6-balsam` para os modelos 3D existentes;
- JSON versionado para persistência e `unittest` para regressão automatizada.

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
│   ├── cenario_inicial.py     # estado mínimo e configuração da GUI
│   ├── grafo.py
│   ├── missao.py             # movimento, estados, progresso e entregas
│   ├── persistencia.py
│   ├── projeto_cidade.py     # grafo e metadados espaciais versionados
│   ├── rota.py               # resultado matemático e validação espacial
│   └── trafegabilidade.py    # grade, largura, segmentos e busca viária
├── ui/
│   ├── animacao_missao.py    # relógio Qt não bloqueante
│   ├── apresentacao_rota.py  # segmentos e marcadores declarativos da rota
│   ├── assets_3d.py          # valida GLB e gerencia o cache Balsam
│   ├── reconhecimento_superficies.py # gera o mapa viário automático
│   ├── camera_orbital.py     # estado matemático da câmera
│   ├── camera_seguidora.py   # câmera em terceira pessoa suavizada
│   ├── cena_3d.qml           # cena Qt Quick 3D única
│   ├── dialogos_editor.py    # confirmação de pontos e pesos (mais legado)
│   ├── editor_cidade.py      # operações espaciais sobre o grafo oficial
│   ├── janela_principal.py   # layout, modos e fluxos do editor
│   ├── tema.py               # paleta azul-marinho e estilos
│   └── visualizacao_3d.py    # ponte QWidget/Qt Quick 3D
├── tests/
├── assets/
│   ├── config/cidade-inicial.json
│   └── models/
│       ├── cidade.glb
│       └── carro.glb
├── gui_main.py
└── main.py
```

## Interface

A janela possui três regiões:

- cidade 3D ocupando aproximadamente 75% da área horizontal;
- painel de controles rolável à direita;
- quatro cartões inferiores para distância, percurso, clientes e status.

Os cartões usam quatro colunas nas larguras maiores e uma grade 2×2 em 960
pixels. O painel lateral mantém rolagem vertical, sem comprimir a cena. O
layout foi verificado em 1920×1080, 1366×768, 1280×720 e 960×640.

Os controles da câmera, do enquadramento, da seção **Editar cidade**, do
cálculo de rotas e da missão animada são funcionais.

Use **Adicionar cliente** e clique no asfalto para cadastrar o primeiro local
de entrega. **Criar rua** passa a ficar disponível quando houver ao menos dois
pontos. Dijkstra permanece bloqueado até existirem extremos distintos e o TSP
informa que é necessário adicionar um cliente. **Abrir** restaura exatamente o
projeto escolhido; **Novo** volta ao estado mínimo sem alterar o arquivo aberto.
Nenhuma sessão anterior é restaurada automaticamente.

### Editor visual

O clique é resolvido por `View3D.pick()` e `pickAll()`. A cena devolve a malha,
o material e `scenePosition`, portanto a posição já considera a hierarquia e a
escala do GLB. Objetos auxiliares não ocultam o asfalto que está abaixo deles,
e as coordenadas lógicas do `QQuickWidget` são convertidas para as dimensões
reais do `View3D`. O grafo usa o plano `(x, z)` da cena e o projeto conserva
também a coordenada vertical completa `(x, y, z)`.

Antes de liberar o editor, o sistema lê os triângulos, transforms, materiais e
cores reais de `cidade.glb` e constrói uma grade espacial. Cada célula é
classificada como rua, calçada, edificação/obstáculo, área verde ou região
incerta. A decisão é local: uma malha grande pode conter regiões diferentes e
uma superfície inferior não prevalece sobre uma calçada ou construção visível
acima dela. Neste asset não há texturas embutidas; os materiais `plane`,
`white.001` e verdes, combinados com altura, inclinação e sobreposição
geométrica, fornecem as pistas verificadas. Cor escura isolada não libera uma
região como rua.

Não existe mais **Classificar superfície** no fluxo principal. Use **Adicionar
ponto**, **Adicionar cliente** ou **Definir depósito** e clique diretamente no
asfalto reconhecido. Calçadas, prédios, áreas verdes e células incertas são
rejeitados com uma explicação. Ao escolher os extremos em **Criar rua**, uma
busca espacial sugere um traçado contido nas ruas; os controles continuam
editáveis antes da confirmação.

O mapa também considera a largura real de `carro.glb` mais a margem de
segurança. Todos os segmentos são amostrados continuamente, não apenas nos
pontos de controle. Uma rua aparece azul acinzentada quando é válida, laranja
quando a análise é inconclusiva e vermelha quando cruza uma região bloqueada
ou não oferece largura suficiente.

O botão **Desfazer** remove primeiro a última curva e depois os extremos; o
botão **Cancelar** descarta toda a prévia. Em **Navegar**, marcadores e linhas
podem ser selecionados para edição, reposicionamento ou exclusão. Exclusões
pedem confirmação. Azul identifica o depósito, verde identifica clientes,
cinza identifica cruzamentos e laranja identifica a operação temporária. Nas
ruas sobrepostas ao modelo, as cores refletem a validação automática descrita
acima. O painel informa permanentemente qual ferramenta está ativa e quantas
ruas estão válidas, incertas ou inválidas.

As ruas podem ser selecionadas em uma faixa de 10 pixels ao redor da linha,
independentemente do zoom. Quando duas linhas ficam dentro dessa faixa, cliques
repetidos no mesmo local alternam as candidatas e o painel mostra a opção
atual. Em **Editar**, o início fica verde, o fim laranja e os controles
intermediários claros. Arraste somente os intermediários; a linha amarela é
uma prévia e nada é gravado antes de **Confirmar**. Um ponto inválido fica
vermelho e volta à posição anterior quando o botão é solto.

**Snap inteligente** encaixa dentro de uma distância limitada em vértices e
segmentos confirmados. Ele não inventa o centro da pista: fora desses alvos, o
ponto real devolvido pelo picking é mantido. Use **Adicionar ponto** e clique
em um segmento para inserir na ordem correta, selecione um controle para
**Remover ponto**, ou use `Ctrl+Z`, `Ctrl+Y`, `Delete`, `Enter` e `Esc` para
desfazer, refazer, remover, confirmar e cancelar. Cancelar restaura integralmente
o traçado original.

Ao confirmar uma rua, o diálogo mostra o comprimento geométrico, o fator
configurável em km/unidade e a sugestão resultante. O peso oficial continua
sendo um campo separado, validado pelo grafo e usado por Dijkstra e TSP.

### Calcular rota

Em **Dijkstra — menor caminho**, escolha qualquer origem e destino do grafo e
pressione **Calcular menor caminho**. Em **Caixeiro Viajante — TSP**, confira o
depósito, marque individualmente até oito clientes ou use **Selecionar todos**
e pressione **Calcular melhor rota**.

A interface chama diretamente os algoritmos de `algorithms/`; ela não contém
uma segunda implementação matemática. No TSP, a ordem de atendimento e o
percurso completo pelas ruas são apresentados separadamente. Os cartões
inferiores exibem peso total, percurso, quantidade prevista de clientes e o
estado real do cálculo.

O destaque ciano segue cada polilinha e seus pontos intermediários. Geometrias
existentes que ainda não foram validadas aparecem em laranja. Quando uma
aresta da rota não possui geometria espacial, o resultado matemático continua
disponível, mas esse trecho não é substituído por uma reta fictícia; ele é
listado como pendente de calibração. Antes da missão, todos os trechos também
são revalidados no mapa automático com a largura do veículo.

**Limpar rota** remove somente o resultado e seus destaques. **Enquadrar rota**
ajusta a câmera aos pontos espaciais disponíveis sem alterar modelo, grafo ou
pesos. Qualquer edição de vértice/rua ou carregamento de outro projeto invalida
o resultado anterior e exige novo cálculo.

### Missão 3D

**Iniciar missão** fica disponível somente quando há uma rota não trivial e
todos os trechos usados possuem polilinhas confirmadas e válidas no mapa
automático. O botão não
recalcula Dijkstra ou TSP: ele consome o resultado exibido. Ruas pendentes são
listadas e precisam ser corrigidas no editor antes da animação.

O controlador independente de Qt avança com o delta de tempo e interpola cada
par de pontos da polilinha. Ele preserva cruzamentos, curvas, sentidos inversos
e repetições de arestas. A distância mostrada em quilômetros continua sendo o
peso oficial do grafo, distribuído proporcionalmente ao avanço geométrico em
cada aresta. O `QTimer` apenas fornece quadros sem bloquear a interface.

Durante a execução é possível pausar, continuar, reiniciar, encerrar e escolher
0,5×, 1×, 2× ou 4×. A edição e a abertura de outro projeto ficam bloqueadas até
**Encerrar missão**, inclusive depois de uma conclusão natural. Reiniciar leva
o carro à origem e limpa as entregas. O painel apresenta o trecho atual,
distâncias percorrida/restante, clientes atendidos e, ao final, um resumo com
algoritmo, alvos, ordem TSP e tempo da simulação.

No TSP, uma entrega só ocorre ao alcançar o próximo cliente da ordem oficial;
passagens incidentais não contam. O carro aguarda aproximadamente um segundo e
retorna ao depósito ao final. Dijkstra registra somente a chegada ao destino.
Trechos percorridos ficam cinza, o atual amarelo e os restantes preservam o
destaque ciano.

### Câmera

- botão esquerdo + arrastar: órbita;
- botão direito + arrastar: deslocamento do alvo;
- roda do mouse: zoom com limites;
- **Enquadrar**: restaura a vista calculada pela caixa real da cidade;
- **Visão aérea**: muda somente a câmera;
- **Focar carro**: enquadra o veículo;
- **Enquadrar rota**: centraliza o percurso espacial calculado;
- **Câmera livre**, **Atrás do carro** e **Aérea**: podem ser alternadas sem
  interromper a missão;
- distância e altura da câmera de perseguição são ajustáveis no painel.

O eixo frontal foi conferido no `carro.glb`: a grade e o para-choque dianteiros
estão no extremo local `-Z`. A transformação do asset aplica a correção de
180° ao yaw da rota, enquanto a câmera é calculada separadamente pela direção
de movimento e suavizada nas curvas.

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

O mapa viário possui cache separado em
`~/.cache/delivery-route/trafegabilidade`. A chave inclui o SHA-256 do conteúdo
de `cidade.glb`, a versão do reconhecedor, escala, resolução e limite de
inclinação. Alterar o modelo ou um desses parâmetros invalida o resultado. O
cache armazena somente metadados derivados e nunca sobrescreve o GLB ou o JSON
do projeto. Na primeira execução, o indicador da cena mostra as etapas e o
percentual da análise; execuções seguintes carregam a grade compactada.

O carregamento é adiado até a área 3D estar visível e possuir dimensões. A
interface diferencia uma árvore QML corretamente carregada de um backend
gráfico realmente capaz de desenhar Qt Quick 3D, evitando interpretar uma tela
escura como sucesso.

## Núcleo matemático

### Quatro conceitos que não devem ser confundidos

- **Rua visual:** células da superfície visível reconhecidas automaticamente
  como via por geometria e material, consultáveis por coordenada `(x, z)`.
- **Aresta do grafo:** conexão abstrata e não direcionada entre dois vértices.
  É a estrutura consultada pelos algoritmos.
- **Peso matemático:** distância oficial positiva, em quilômetros, atribuída à
  aresta. É esse valor — não o comprimento visual — que Dijkstra e TSP somam.
- **Traçado espacial:** polilinha 3D ordenada entre os extremos, incluindo as
  curvas marcadas pelo usuário. Ela desenha o destaque e guia o carro, mas não
  altera por conta própria o peso oficial.
- **Estacionamento inicial:** pose física opcional do carro, associada ao
  depósito sem mover o vértice lógico. A pegada completa do `carro.glb` é
  validada sobre a grade automática de rua antes do uso.

`models/grafo.py` mantém vértices, arestas, pesos e invariantes do grafo.
`algorithms/dijkstra.py` parte da origem, relaxa as arestas com uma fila de
prioridade e reconstrói o caminho mínimo pelos predecessores, em
`O((V + E) log V)`. Pesos negativos são proibidos pelo modelo.
`algorithms/caixeiro_viajante.py` avalia exatamente as permutações dos clientes,
com custo fatorial `O(C! · C)` e limite padrão de oito clientes. Para cada par
de paradas, a distância e o caminho real são obtidos com Dijkstra; por isso a
ordem de entregas pode ser menor que o percurso completo pelos cruzamentos.

O cenário de demonstração confirma:

- Dijkstra de `D` até `B`: `D → X → A → B`, com 6 km;
- TSP: ordem `D → A → B → C → D` e percurso completo
  `D → X → A → B → C → D`, com 15 km e seis ordens avaliadas.

## Persistência

Os botões **Salvar** e **Abrir** usam o formato versionado de
`models/projeto_cidade.py`. Ele armazena o grafo, posições 3D, polilinhas,
classificações manuais legadas, fator de conversão, referências dos GLBs e, quando
disponível, `editor_3d.estacionamento_inicial`. Os binários dos modelos não são
incorporados ao JSON. Arquivos antigos de
`models/persistencia.py` continuam aceitos; seus vértices sem posição espacial
recebem uma disposição inicial aproximada e podem ser reposicionados sobre
ruas reconhecidas. As classificações antigas são aceitas e preservadas ao
salvar, mas têm prioridade inferior ao reconhecimento atual. O carregamento é
transacional: um JSON inválido não
substitui o projeto aberto.

O cenário `delivery-route-cidade-completa-corrigida.json` mantém grafo, pesos e
rede viária do original e acrescenta somente a vaga validada próxima a `D`.
As capturas OpenGL ficam em `evidencias/estacionamento/`.

## Roteiro reproduzível de demonstração acadêmica

Este roteiro não depende de coordenadas prontas nem inventa ruas. Cada clique
deve ser feito sobre uma via realmente visível na cidade carregada:

1. execute `python3 gui_main.py` e aguarde o mapa viário e a **CENA 3D PRONTA**;
2. use **Enquadrar** ou **Aérea** para localizar uma faixa contínua de asfalto;
3. ative **Definir depósito**, clique sobre a via reconhecida e cadastre o depósito;
4. ative **Adicionar cliente**, clique em outro ponto da mesma rede e cadastre
   o primeiro cliente;
5. repita a etapa anterior para os demais clientes desejados;
6. crie os cruzamentos necessários com **Adicionar ponto**;
7. em **Criar rua**, selecione dois marcadores conectados pela via real;
8. confira a sugestão automática e ajuste os controles somente se necessário;
9. pressione **Confirmar**, compare comprimento geométrico e sugestão, informe
    o peso oficial em quilômetros e salve a rua;
10. repita as etapas 7–9 até obter uma rede conectada; confirme que as ruas
    válidas estão azuis e que não há trechos incertos ou inválidos;
11. escolha **Dijkstra**, defina origem/destino, calcule e confira distância,
    percurso completo, clientes no percurso e destaque na cidade;
12. limpe a rota, escolha **TSP**, marque clientes e confira separadamente a
    ordem de atendimento e o percurso completo;
13. inicie a missão, alterne câmera e velocidade, pause e confirme que o carro
    fica imóvel; depois continue até entregas e retorno ao depósito;
14. encerre a missão, salve o projeto em JSON, feche e abra o arquivo novamente;
15. recalcule a rota e confirme que pontos, pesos e curvas persistiram e foram
    revalidados contra o mesmo conteúdo de `cidade.glb`.

Se um clique cair em calçada, prédio, área verde ou região incerta, o editor
deve rejeitá-lo e explicar a classificação automática encontrada.

## Limitações conhecidas

- o reconhecedor é conservador: regiões sem evidência suficiente continuam
  incertas e precisam de ajuste do traçado, não de classificação manual;
- o TSP é exato e propositalmente limitado a oito clientes;
- a missão exige traçados espaciais confirmados para todos os trechos da rota;
- a renderização 3D depende de driver/backend gráfico compatível com QRhi;
- o projeto não contém navegação por GPS, tráfego dinâmico ou colisão física.

## Testes

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
python3 -m compileall -q algorithms models ui main.py gui_main.py tests
```

A suíte cobre o núcleo matemático, os formatos novo e legado, reconhecimento e
cache de superfícies, largura do veículo, busca viária,
criação/edição/exclusão de vértices e ruas, coordenadas, curvas,
pesos, consistência visual, ponte de picking, seleção e execução de
Dijkstra/TSP, ordem de atendimento, percurso completo, trechos pendentes,
invalidação, cartões, destaques espaciais, inspeção dos GLBs, câmera e
inicialização QML, interpolação temporal, orientação, arestas inversas e
repetidas, pausa/continuação/reinício, velocidades, progresso oficial,
entregas TSP e câmera de perseguição.

O backend `offscreen` valida a estrutura sem oferecer uma API 3D real. A
validação desta versão também foi executada com OpenGL: cidade e carro foram
materializados; pontos de uma faixa contínua de pavimento foram obtidos por
`View3D.pick()`; o `carro.glb` avançou sobre ela de `x=-1,379621` até
`x=-0,667879`, permaneceu imóvel durante a pausa e terminou no ponto exato. A
câmera de perseguição e o resumo final também foram capturados na cena real.
Além do teste gráfico, o mapa automático foi conferido no `cidade.glb` real e
todos os trechos de `delivery-route-cidade-completa.json` passaram pela
validação contínua com a largura e margem do `carro.glb`.
