# Delivery Route

Sistema acadêmico para representar uma cidade como um grafo e otimizar rotas de
entrega. A aplicação encontra caminhos mínimos com Dijkstra e calcula rotas
ótimas de entrega com uma solução exata do Problema do Caixeiro Viajante.

O projeto também possui uma primeira interface desktop em PySide6, com tema
escuro e visualizações intercambiáveis de cidade e de grafo.

## Objetivo e funcionalidades

O objetivo é demonstrar, em um cenário pequeno e reproduzível, como um grafo
ponderado pode representar ruas e locais de uma cidade. O projeto oferece:

- modelo de grafo não direcionado com depósito, clientes e cruzamentos;
- menor caminho entre dois locais com Dijkstra;
- rota exata de entregas com TSP por força bruta;
- visualizações Cidade e Grafo sobre o mesmo modelo;
- editor de vértices e arestas, com validação das invariantes;
- salvamento e carregamento de projetos em JSON versionado;
- execução passo a passo manual dos dois algoritmos;
- testes automatizados de modelo, algoritmos, interface e persistência.

## Estrutura atual

```text
.
├── main.py                 # demonstração do grafo, Dijkstra e TSP
├── gui_main.py             # ponto de entrada da interface gráfica
├── models/
│   ├── grafo.py            # vértices, arestas e grafo
│   └── persistencia.py     # formato JSON e validação de projetos
├── algorithms/
│   ├── dijkstra.py         # caminhos mínimos e histórico da execução
│   └── caixeiro_viajante.py # rota ótima para vários clientes
├── ui/                     # componentes da interface PySide6
│   ├── janela_principal.py # janela e coordenação dos painéis
│   ├── mapa_cidade.py      # visualização logística da cidade
│   ├── visualizador_grafo.py # visualização matemática
│   ├── visualizacao_base.py  # seleção, zoom e posicionamento
│   ├── painel_resultados.py # cartões de resultados dos algoritmos
│   ├── painel_passos.py      # controles da execução didática
│   ├── execucao_passos.py    # sessão e adaptação dos históricos
│   ├── editor_dialogos.py    # formulários de vértices e arestas
│   └── estilos.py          # paleta e QSS
├── data/                   # reservado para dados de cenários
├── tests/
│   ├── test_grafo.py       # testes do modelo
│   ├── test_dijkstra.py    # testes dos caminhos mínimos
│   ├── test_caixeiro_viajante.py # testes da rota ótima
│   ├── test_interface.py   # testes gráficos em modo offscreen
│   ├── test_integracao_interface.py # testes dos cálculos pela UI
│   ├── test_editor_interface.py # testes do editor interativo
│   ├── test_passos.py       # históricos estruturados dos algoritmos
│   ├── test_passos_interface.py # controles e destaques passo a passo
│   ├── test_persistencia.py # testes do formato JSON
│   └── test_persistencia_interface.py # integração dos arquivos com a UI
├── requirements.txt
├── .gitignore
└── README.md
```

## Modelo de grafo

A cidade é representada por um **grafo não direcionado e ponderado**. Depósitos,
clientes e cruzamentos são os vértices. Cada rua é uma aresta armazenada nos dois
sentidos, e seu peso positivo corresponde à distância em quilômetros. As
conexões são mantidas em listas de adjacência.

O módulo valida identificadores duplicados, vértices inexistentes, laços,
arestas repetidas, pesos inválidos e a existência de no máximo um depósito
principal.

## Cenário de demonstração

`criar_cenario_exemplo()` constrói sempre o mesmo grafo, usado pela demonstração
terminal, pela interface inicial e pelos testes. As posições são coordenadas
apenas para a apresentação visual.

### Vértices

| ID | Nome | Tipo | Posição |
| --- | --- | --- | --- |
| D | Depósito Central | depósito | (0, 0) |
| X | Cruzamento | cruzamento | (2, 1) |
| A | Cliente A | cliente | (3, 0) |
| B | Cliente B | cliente | (5, 2) |
| C | Cliente C | cliente | (2, 4) |

### Ruas

| Origem | Destino | Peso |
| --- | --- | ---: |
| D | X | 2 km |
| X | A | 1 km |
| A | B | 3 km |
| B | C | 2 km |
| C | D | 7 km |
| X | B | 5 km |
| A | C | 6 km |

Como as ruas são bidirecionais, cada entrada representa os dois sentidos.
Os resultados de referência são:

- Dijkstra de `D` até `B`: `D → X → A → B`, distância de **6 km**;
- TSP com `A`, `B` e `C`: ordem de atendimento `D → A → B → C → D`,
  percurso completo `D → X → A → B → C → D`, distância ótima de **15 km**;
- o TSP avalia **6 ordens** (`3!`) nesse cenário.

## Algoritmo de Dijkstra

Dijkstra calcula a menor distância de uma origem até os demais vértices de um
grafo cujas arestas têm pesos não negativos. No Delivery Route, uma fila de
prioridade seleciona repetidamente o local com a menor distância provisória. As
arestas vizinhas são então relaxadas: quando uma rota menor é encontrada, sua
distância e seu predecessor são atualizados.

A função `dijkstra` encerra ao encontrar o destino e retorna um
`ResultadoDijkstra`, com origem, destino, caminho ordenado, distância e status.
Um destino inalcançável é representado por caminho vazio, distância
`math.inf` e `encontrado=False`.

A função `dijkstra_todos` reaproveita a mesma implementação para calcular as
distâncias da origem a todos os vértices. O resultado também permite reconstruir
um caminho específico. Isso prepara o projeto para consumir essas distâncias em
etapas futuras, mas Dijkstra sozinho **não** resolve o problema de visitar vários
clientes na menor rota total (TSP).

Exemplo:

```python
from algorithms.dijkstra import dijkstra, dijkstra_todos
from models.grafo import criar_cenario_exemplo

grafo = criar_cenario_exemplo()
resultado = dijkstra(grafo, "D", "B")
print(resultado.caminho)          # ['D', 'X', 'A', 'B']
print(resultado.distancia_total)  # 6.0

todos = dijkstra_todos(grafo, "D")
print(todos.reconstruir_caminho("C"))  # ['D', 'C']
```

### Registro das etapas

Passe `registrar_etapas=True` a qualquer uma das funções para guardar uma
fotografia de cada vértice processado. Cada etapa registra as distâncias
provisórias, os predecessores, os vértices processados, as arestas examinadas e
as atualizações realizadas. Esse histórico é apenas dado estruturado: não há
esperas ou animação no algoritmo; a interface o apresenta sob controle manual do
usuário. Por padrão o registro fica desligado para economizar memória.

## Problema do Caixeiro Viajante

O Problema do Caixeiro Viajante (TSP) procura a menor rota que sai do depósito,
visita cada cliente selecionado uma vez como parada de atendimento e retorna ao
depósito. Nesta etapa usamos uma solução exata por força bruta com
`itertools.permutations`. Ela é adequada ao cenário acadêmico pequeno e garante
a rota ótima, além de tornar explícita a comparação de todas as sequências.

Antes das permutações, o sistema executa `dijkstra_todos` a partir de cada local
relevante. Assim, o custo entre duas paradas é sempre o menor deslocamento real
pelas ruas do grafo. O resultado diferencia:

- **ordem das entregas:** depósito e clientes na sequência de atendimento;
- **percurso completo:** todos os vértices realmente atravessados, inclusive
  cruzamentos ou clientes usados apenas como passagem.

Isso também diferencia os dois problemas: Dijkstra encontra o menor caminho
entre locais; o TSP compara ordens de visita para minimizar a rota completa.

Como a quantidade de permutações cresce de forma fatorial, a execução exata
aceita por padrão até **8 clientes**. O parâmetro `limite_clientes` permite
configurar outro limite; o sistema nunca troca silenciosamente para uma solução
aproximada.

Exemplo:

```python
from algorithms.caixeiro_viajante import caixeiro_viajante
from models.grafo import criar_cenario_exemplo

grafo = criar_cenario_exemplo()

# None usa todos os clientes; uma lista vazia representa nenhuma entrega.
resultado = caixeiro_viajante(grafo, clientes=None)
print(resultado.ordem_entregas)       # ['D', 'A', 'B', 'C', 'D']
print(resultado.percurso_completo)    # ['D', 'X', 'A', 'B', 'C', 'D']
print(resultado.distancia_total)      # 15.0

parcial = caixeiro_viajante(grafo, clientes=["A", "B"])
```

## Requisitos

- Python 3.11 ou superior.
- PySide6 6.5 ou superior (necessário para `gui_main.py` e para os testes de
  interface; os módulos de modelo e algoritmos usam apenas a biblioteca
  padrão).

Instale a dependência em um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Em um ambiente limpo, os comandos acima são suficientes; o projeto não depende
de pacotes instalados em diretórios temporários ou de arquivos externos.

## Executar a interface gráfica

```bash
python3 gui_main.py
```

A janela inicia com o cenário de demonstração. Os botões **Cidade** e **Grafo**
alternam duas representações do mesmo objeto `Grafo`. É possível selecionar um
local, consultar suas conexões, aplicar zoom com a roda do mouse, mover a área
visível por arraste e restaurar o enquadramento.

### Calcular uma rota pela interface

No painel **Otimização de rotas**, selecione `Dijkstra — Menor caminho`, escolha
origem e destino e clique em **Calcular menor caminho**. O resultado mostra o
caminho, a distância e o status; por exemplo, `D` até `B` produz `D → X → A → B`
com 6 km.

Para entregas, selecione `Caixeiro Viajante — Rota de entregas`, marque os
clientes desejados e clique em **Calcular melhor rota**. O cenário completo
produz ordem `D → A → B → C → D`, percurso `D → X → A → B → C → D`, distância
15 km, 3 clientes e 6 sequências avaliadas. A lista permite desmarcar clientes
individualmente, inclusive todos eles para obter a rota trivial no depósito.

Após o cálculo, o mesmo resultado é mantido em memória enquanto Cidade e Grafo
são alternados. As arestas do percurso completo ficam destacadas em verde nas
duas visualizações. **Limpar rota** remove os destaques e os cartões, sem recriar
nem alterar o grafo.

### Editar o cenário

Use os botões **Visualização** e **Edição** no cabeçalho para habilitar o editor.
No modo de edição é possível adicionar, alterar e remover locais e ruas. Os
formulários validam identificadores, nomes, tipos, coordenadas e pesos usando as
operações do modelo, mantendo um único depósito e as arestas simétricas. Cada
alteração atualiza Cidade, Grafo e os seletores de rota, invalida o resultado
anterior e pede um novo cálculo. **Restaurar exemplo** reconstrói o cenário
original e pede confirmação quando houver alterações em memória.

O botão de cálculo fica temporariamente desabilitado durante uma execução. Erros
esperados — como origem inválida, destino inalcançável, ausência de depósito ou
limite do TSP — aparecem no painel sem encerrar a aplicação.

Não há persistência de resultados, destaques, seleções ou animações: esses
estados são recalculados ao abrir um projeto.

### Execução passo a passo

No painel **Passo a passo**, use **Iniciar** depois de escolher Dijkstra ou TSP.
Os botões **|<**, **Anterior**, **Próximo** e **>|** navegam pelo histórico sem
iniciar outro cálculo ao alternar entre Cidade e Grafo. A descrição informa a
seleção do vértice, os relaxamentos, as distâncias provisórias e, no TSP, cada
ordem de clientes avaliada e a melhor solução conhecida. Na etapa final, o
resultado normal aparece no painel de resultados; **Encerrar** remove os
destaques didáticos e mantém a rota final quando ela já foi concluída.

O histórico de Dijkstra registra as iterações e uma conclusão. O TSP exato
registra uma etapa por permutação, além da inicialização e conclusão; por isso o
volume cresce fatorialmente e continua limitado ao máximo de clientes definido
para o algoritmo. O histórico é temporário e nunca é salvo no JSON.

### Salvar e abrir projetos

O menu **Projeto** oferece **Abrir projeto**, **Salvar**, **Salvar como...** e a
restauração do cenário de demonstração. O primeiro salvamento solicita um
arquivo `.json`; depois, **Salvar** reutiliza o caminho associado ao projeto.
Alterações no editor marcam o projeto como pendente (`*` no título). Ao abrir,
restaurar ou fechar com alterações pendentes, a interface permite salvar,
descartar ou cancelar.

O formato versão 1 usa uma única entrada para cada aresta não direcionada:

```json
{
  "formato": "delivery-route-grafo",
  "versao": 1,
  "deposito": "D",
  "vertices": [
    {"identificador": "D", "nome": "Depósito Central",
     "tipo": "depósito", "x": 0, "y": 0}
  ],
  "arestas": [
    {"origem": "D", "destino": "X", "peso": 2}
  ]
}
```

`models/persistencia.py` valida versão, tipos, nomes e identificadores,
referências, depósito único, laços, duplicidades e pesos antes de substituir o
grafo atual. O salvamento usa arquivo temporário e substituição atômica. Arquivos
JSON não compatíveis são rejeitados sem alterar o projeto aberto.

Limitações: o formato ainda não possui migrações para versões futuras, não salva
preferências da interface e as edições continuam restritas à sessão até serem
salvas explicitamente.

## Executar a demonstração

Na raiz do projeto:

```bash
python3 main.py
```

A demonstração monta o cenário fictício, exibe seus vértices e conexões, calcula
o caminho mínimo de `D` até `B` e encontra a rota ótima que atende todos os
clientes e retorna ao depósito.

## Executar os testes

```bash
python3 -m unittest discover -s tests -v
```

Com PySide6 instalado, a suíte inclui os testes gráficos. Sem essa dependência,
os testes de interface são automaticamente ignorados e somente os módulos sem
Qt são executados.

Em ambientes sem servidor gráfico, os testes da interface podem ser executados
em modo headless:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```
