# Delivery Route — Grafos e otimização de rotas

Projeto acadêmico em Python para representar uma rede de entregas como um
grafo não direcionado e ponderado e estudar dois problemas clássicos:

- menor caminho entre dois pontos, resolvido com Dijkstra;
- melhor circuito de entregas, resolvido exatamente como um Problema do
  Caixeiro Viajante (TSP).

Esta versão funciona inteiramente no terminal e não possui interface gráfica.
Uma nova interface poderá ser construída futuramente sem alterar o núcleo
matemático.

## Requisitos

- Python 3.10 ou mais recente;
- nenhuma dependência externa.

Os algoritmos e a persistência usam apenas a biblioteca padrão do Python. A
pasta opcional `assets/` guarda modelos antigos para eventual uso futuro, mas
não participa da execução.

## Estrutura

```text
.
├── algorithms/
│   ├── dijkstra.py
│   └── caixeiro_viajante.py
├── models/
│   ├── grafo.py
│   └── persistencia.py
├── tests/
│   ├── test_grafo.py
│   ├── test_dijkstra.py
│   ├── test_caixeiro_viajante.py
│   └── test_persistencia.py
├── assets/models/        # opcional; não é usado pelo núcleo
├── main.py
└── requirements.txt
```

## Modelo do grafo

`models/grafo.py` implementa um grafo não direcionado com lista de
adjacências. Cada `Vertice` possui identificador, nome, tipo (depósito,
cliente ou cruzamento) e coordenadas. Cada `Aresta` liga dois vértices e tem um
peso positivo e finito, interpretado como distância em quilômetros.

O modelo permite adicionar, editar e remover vértices e arestas, consultar
vizinhos e pesos, identificar o depósito e os clientes e validar invariantes
como nomes únicos, ausência de laços e existência de no máximo um depósito.

Exemplo de construção por código:

```python
from models.grafo import Grafo, TipoVertice, Vertice

grafo = Grafo()
grafo.adicionar_vertice(
    Vertice("D", "Depósito", TipoVertice.DEPOSITO, 0, 0)
)
grafo.adicionar_vertice(
    Vertice("A", "Cliente A", TipoVertice.CLIENTE, 2, 1)
)
grafo.adicionar_aresta("D", "A", 3.5)

grafo.atualizar_peso_aresta("D", "A", 4)
grafo.atualizar_vertice(
    "A", nome="Cliente A", tipo=TipoVertice.CLIENTE, x=3, y=2
)
```

Também estão disponíveis `remover_aresta` e `remover_vertice`. A função
`criar_cenario_exemplo()` monta o cenário compartilhado pela demonstração e
pelos testes.

## Dijkstra

`algorithms/dijkstra.py` calcula o menor caminho entre uma origem e um destino
com pesos positivos. O resultado informa o percurso, a distância total e se o
destino foi alcançado. `dijkstra_todos` calcula as menores distâncias da origem
para todos os vértices e é reutilizado pelo TSP.

Com uma fila de prioridade, a complexidade de tempo é
`O((V + E) log V)` e a de espaço é `O(V + E)`.

```python
from algorithms.dijkstra import dijkstra
from models.grafo import criar_cenario_exemplo

resultado = dijkstra(criar_cenario_exemplo(), "D", "B")
print(resultado.caminho)          # ['D', 'X', 'A', 'B']
print(resultado.distancia_total)  # 6.0
```

## Caixeiro Viajante

`algorithms/caixeiro_viajante.py` usa a solução exata existente por força
bruta. Todas as ordens dos clientes são avaliadas; as distâncias entre os
pontos relevantes são obtidas por Dijkstra. O resultado distingue a ordem de
atendimento do percurso completo no grafo.

Para `C` clientes, a enumeração custa `O(C! · C)`. O pré-cálculo dos menores
caminhos custa `O((C + 1)(V + E) log V)`. Por isso, o limite padrão é de oito
clientes e pode ser configurado na chamada.

```python
from algorithms.caixeiro_viajante import caixeiro_viajante
from models.grafo import criar_cenario_exemplo

resultado = caixeiro_viajante(criar_cenario_exemplo())
print(resultado.ordem_entregas)
print(resultado.percurso_completo)
print(resultado.distancia_total)
```

## Cenário de demonstração

Execute:

```bash
python3 main.py
```

A demonstração lista os vértices e as arestas e confirma:

- Dijkstra de `D` até `B`: `D → X → A → B`, com 6 km;
- TSP para `A`, `B` e `C`: ordem ótima
  `D → A → B → C → D`, percurso completo
  `D → X → A → B → C → D`, com 15 km;
- seis ordens de atendimento avaliadas.

## Persistência JSON

`models/persistencia.py` salva e carrega somente dados do grafo: versão do
formato, depósito, vértices, tipos, coordenadas, arestas e pesos. O carregamento
valida todo o documento antes de devolver o novo grafo e não contém estado de
interface, câmera ou renderização.

```python
from models.grafo import criar_cenario_exemplo
from models.persistencia import carregar_grafo, salvar_grafo

salvar_grafo(criar_cenario_exemplo(), "cenario.json")
grafo = carregar_grafo("cenario.json")
```

## Testes e validação

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q algorithms models main.py tests
```

Os testes cobrem as invariantes e operações do grafo, caminhos mínimos,
entradas inválidas e vértices inacessíveis, solução exata e limite do TSP e a
serialização JSON.
