# Delivery Route

Sistema acadêmico para representar uma cidade como um grafo e, em etapas
futuras, otimizar rotas de entrega. A versão atual representa a cidade como um
grafo, encontra caminhos mínimos com Dijkstra e calcula rotas ótimas de entrega
com uma solução exata do Problema do Caixeiro Viajante.

## Estrutura atual

```text
.
├── main.py                 # demonstração do grafo, Dijkstra e TSP
├── models/
│   └── grafo.py            # vértices, arestas e grafo
├── algorithms/
│   ├── dijkstra.py         # caminhos mínimos e histórico da execução
│   └── caixeiro_viajante.py # rota ótima para vários clientes
├── ui/                     # reservado para a interface PySide6
├── data/                   # reservado para dados de cenários
├── tests/
│   ├── test_grafo.py       # testes do modelo
│   ├── test_dijkstra.py    # testes dos caminhos mínimos
│   └── test_caixeiro_viajante.py # testes da rota ótima
├── requirements.txt
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
esperas ou animação no algoritmo, e a futura interface poderá apresentá-lo na
velocidade desejada. Por padrão o registro fica desligado para economizar memória.

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
- Nenhuma dependência externa nesta etapa. O PySide6 será incorporado quando a
  interface gráfica for desenvolvida.

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
