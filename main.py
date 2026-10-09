"""Demonstração em modo texto do Delivery Route."""

from algorithms.caixeiro_viajante import caixeiro_viajante
from algorithms.dijkstra import dijkstra
from models.grafo import criar_cenario_exemplo


def main() -> None:
    """Apresenta o cenário fictício e calcula um caminho mínimo."""
    grafo = criar_cenario_exemplo()

    print("===== DELIVERY ROUTE =====\n")
    print("=== Vértices cadastrados ===")
    for vertice in grafo.listar_vertices():
        print(
            f"{vertice.identificador}: {vertice.nome} "
            f"({vertice.tipo.value}) - posição ({vertice.x:g}, {vertice.y:g})"
        )

    print("\n=== Conexões ===")
    for aresta in grafo.listar_arestas():
        print(
            f"{aresta.origem.identificador} ↔ "
            f"{aresta.destino.identificador}: {aresta.peso:g} km"
        )

    deposito = grafo.obter_deposito()
    print("\n=== Depósito principal ===")
    if deposito is None:
        print("Nenhum depósito foi definido.")
    else:
        print(f"{deposito.identificador}: {deposito.nome}")

    print("\n=== Clientes ===")
    for cliente in grafo.listar_clientes():
        print(f"{cliente.identificador}: {cliente.nome}")

    origem_id = "D"
    destino_id = "B"
    resultado = dijkstra(grafo, origem_id, destino_id)
    origem = grafo.obter_vertice(origem_id)
    destino = grafo.obter_vertice(destino_id)

    print("\n=== Menor rota ===")
    print("Algoritmo: Dijkstra")
    print(f"Origem: {origem.nome} ({origem.identificador})")
    print(f"Destino: {destino.nome} ({destino.identificador})")
    if resultado.encontrado:
        print(f"Menor caminho: {' -> '.join(resultado.caminho)}")
        print(f"Distância total: {resultado.distancia_total:g} km")
        print("Status: Caminho encontrado")
    else:
        print("Menor caminho: inexistente")
        print("Distância total: infinita")
        print("Status: Destino inalcançável")

    resultado_tsp = caixeiro_viajante(grafo)
    print("\n===================================")
    print("Algoritmo: Caixeiro Viajante")
    print(f"Depósito: {deposito.nome if deposito else 'Não definido'}")
    print("Clientes:")
    for cliente in grafo.listar_clientes():
        print(f"- {cliente.nome}")
    if resultado_tsp.encontrada:
        print(f"Ordem das entregas: {' -> '.join(resultado_tsp.ordem_entregas)}")
        print(f"Percurso completo: {' -> '.join(resultado_tsp.percurso_completo)}")
        print(f"Distância total: {resultado_tsp.distancia_total:g} km")
        print(
            "Clientes atendidos: "
            f"{resultado_tsp.quantidade_clientes_atendidos}"
        )
        print(f"Rotas avaliadas: {resultado_tsp.sequencias_avaliadas}")
        print("Status: Rota ótima encontrada")
    else:
        print("Status: Não existe rota viável")
    print("===================================")


if __name__ == "__main__":
    main()
