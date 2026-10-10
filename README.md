# Delivery Route — Cidade 3D

Aplicação acadêmica em PySide6 para configurar ruas sobre uma cidade GLB,
calcular rotas de entrega e acompanhar o carro em uma missão 3D. A janela
entregue (`gui_main.py`) mostra somente a Cidade 3D; os visualizadores 2D e de
grafo permanecem no repositório apenas para compatibilidade dos módulos e dos
testes antigos, mas não são criados pelo ponto de entrada.

## Executar

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-3d.txt  # Qt Quick 3D/Balsam
python3 gui_main.py
```

Os modelos padrão são `assets/models/cidade.glb` e `assets/models/carro.glb`.
O Qt Quick 3D converte os GLBs uma vez com `pyside6-balsam`, em cache
temporário, preservando materiais e texturas.

## Fluxo da interface

* **Editar cidade**: navegação orbital, classificação manual do pavimento,
  pontos de depósito/clientes/cruzamentos e ruas por polilinhas. O clique é
  resolvido com `View3D.pick`; um nome de malha genérico ou um prédio nunca é
  aceito como rua sem uma superfície trafegável confirmada.
* **Calcular rota**: escolha Dijkstra (origem/destino) ou Caixeiro Viajante
  (depósito/clientes). O resultado é calculado uma única vez pelos módulos em
  `algorithms/` e destacado na Cidade 3D; pesos oficiais continuam sendo os do
  `models.grafo.Grafo`.
* **Missão 3D**: iniciar, pausar, continuar e reiniciar o percurso. A câmera
  atrás do carro é separada da câmera livre e a missão é bloqueada enquanto
  faltar geometria viária confirmada para alguma aresta da rota.

Na câmera livre: botão esquerdo + arrastar orbita, botão direito + arrastar
desloca e a rodinha aplica zoom. **Enquadrar cidade** e **Foco carro** não
alteram a geometria.

## Arquitetura

* `models/grafo.py`: vértices, arestas, pesos e invariantes (fonte oficial dos
  algoritmos).
* `algorithms/dijkstra.py` e `algorithms/caixeiro_viajante.py`: implementações
  existentes, sem lógica duplicada na UI.
* `models/persistencia.py`: formato de grafo legado, ainda compatível.
* `models/projeto_3d.py`: formato versionado que referencia os GLBs e salva
  grafo, mapeamento espacial, superfícies classificadas e ruas configuradas;
  nunca incorpora a geometria binária do GLB.
* `ui/janela_principal_3d.py`: janela exclusiva 3D e coordenação dos três
  painéis.
* `ui/editor_ruas_3d.py`: máquina de estados pura para picking, superfícies,
  polilinhas, conversão de comprimento e validação das conexões.
* `ui/cidade_3d.py`: mapeamento espacial, marcadores, animação e estados de
  câmera/missão.
* `ui/renderizador_qtquick3d.py` e `ui/glb_scene.qml`: importação Balsam,
  diagnóstico, View3D, raycast, câmera e marcadores.

## Persistência e compatibilidade

Use **Projeto → Salvar projeto 3D** para salvar a configuração completa. O
carregador valida versão, grafo, referências, coordenadas e superfícies antes
de trocar o estado atual. Arquivos de grafo do formato anterior continuam
podendo ser lidos pelos módulos de persistência existentes.

## Testes

```bash
QT_QPA_PLATFORM=offscreen ./.venv/bin/python -m unittest discover -s tests
./.venv/bin/python -m py_compile gui_main.py models/*.py ui/*.py tests/*.py
./.venv/bin/pyside6-qmllint ui/glb_scene.qml
```

O modo `offscreen` valida APIs, QML, algoritmos e estados, mas não comprova
uma imagem 3D. Para a verificação final, execute em uma sessão Linux com
OpenGL/Wayland/XCB, abra a janela, clique no asfalto para classificar uma
superfície, crie as ruas, calcule a rota e inicie a missão.

## Diagnóstico gráfico

Falhas do Qt Quick 3D são registradas no próprio renderizador: backend QRhi,
dimensões do widget/raiz QML/View3D, carregamento dos `Loader3D`, recursos
`.mesh`/texturas, câmera, frames e resultados do `View3D.pick`. Uma área com
dimensão zero ou sem backend renderizável permanece explicitamente indicada ao
usuário, em vez de uma tela preta silenciosa.
