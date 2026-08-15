# Squadrats — análise detalhada (concelho/município) para todo o clube

**Estado:** brainstorm inicial, nada implementado. Escrito a pedido explícito do José em 15 Ago 2026, depois de fechar o suporte a Espanha+Andorra+Alemanha para a análise pessoal dele. **Não construir sem revisão** — há decisões de arquitectura e de UI por confirmar antes de gastar tempo de computação nisto (o cálculo geográfico de hoje já levou ~35 min só para 1 pessoa + 4 países).

---

## 1. Onde estamos hoje (ponto de partida real, não hipotético)

- `pipeline.py` (só corre para o José, `JOSE_UID`) já classifica cada square por país/distrito/concelho via `classify.py` — isto é o motor todo, reutilizável tal como está.
- `fetch_club_koms.py` e `fetch_club_squares.py` (os scripts que servem os outros 4 membros — Carolina, Inês S., Xeira, Pedro) **não chamam `Classifier` nenhuma vez**. Só sabem totais (`fetch_club_koms.py`) e coordenadas/bitmask de squares (`fetch_club_squares.py` → `club.json`). Zero classificação geográfica existe para eles hoje.
- `index.html` está hardcoded a um único atleta (José) — não há selector de atleta, nem estrutura de dados pensada para "5 pessoas, cada uma com a sua tabela".

Ou seja: isto não é "ligar um botão que falta" — é uma extensão real em duas frentes independentes (backend: classificar squares de mais 4 pessoas; frontend: mostrar 5 conjuntos de dados em vez de 1).

---

## 2. Volume de dados — o problema que já tinhas identificado

Por pessoa, ao nível mais fino já suportado:
- PT: 308 concelhos
- ES: 8132 municípios
- DE: 10978 municípios
- AD: 7 paróquias

**~19425 regiões por pessoa.** Vezes 5 pessoas = **~97000 linhas** se fosse tudo despejado numa tabela só. Isto confirma o que já tinhas dito — não dá para ser só "a mesma tabela com uma coluna a mais".

Mas nem todos os membros tocam em todos os países (já sabíamos isto da análise geográfica anterior):
- Carolina, Inês S.: só PT+ES
- Xeira: PT (+Madeira, já é PT)+ES
- Pedro: PT+ES+DE+Marrocos (Marrocos ainda sem fronteiras nenhumas)

Isso já corta bastante — não é preciso computar Alemanha para toda a gente, só para quem lá esteve.

---

## 3. Backend — o que muda

### 3.1 Extensão mínima e reutilizável
`fetch_club_squares.py` (ou um script novo `classify_club.py`, a decidir) passa a:
1. Para cada atleta em `ATHLETES`, obter os squares (já faz isto).
2. Instanciar o `Classifier` uma vez (já existe, custa ~1.7s a construir — pago uma vez por *run*, não por atleta).
3. Chamar `classify()` por square, tal como `pipeline.py` já faz para o José.
4. Agregar por concelho/município, tal como `grid_totals.json` + `stats.json` já fazem — **reaproveitar exactamente essa lógica**, não inventar uma nova.

### 3.2 Onde publicar os totais — evitar um stats.json gigante
Ideia (a validar): um ficheiro por atleta, `data/stats_<uid_curto>.json` ou `data/club_regioes.json` com estrutura `{uid: {by_concelho: {...}, by_municipio_es: {...}, ...}}`, carregado **só quando o utilizador escolhe ver esse atleta** (lazy fetch), não no `loadAll()` de arranque que carrega tudo de uma vez hoje. Isto evita que o mapa do José fique 5x mais lento a abrir só para dados que ele não vê por defeito.

### 3.3 Custo de computação
O `compute_grid_totals.py` de hoje (candidatos/totais da grelha) **não muda** — os totais por região já são por-região, não por-atleta (é sempre o mesmo mapa dividido nas mesmas células, o "quem capturou o quê" é que varia). O trabalho extra é só a classificação dos squares reais de cada atleta (rápido, é por-square não por-célula-candidata) e a agregação — não é preciso repetir a parte lenta (z17 unificado).

---

## 4. Frontend — opções de display (a decisão que falta)

### Opção A — Selector de atleta, reaproveitar a UI actual (recomendo começar aqui)
Um dropdown/pills "A ver: José ▾" no topo da sheet. Ao mudar, troca só os dados (`cache.stats` equivalente por atleta), a tabela/mapa/cores são exactamente os mesmos componentes já construídos hoje.
- **Prós:** zero UI nova, reaproveita 100% do trabalho de hoje (tabela, toggle de país, cores por região). Esforço concentrado no backend.
- **Contras:** não mostra comparação entre membros de forma nenhuma — é "um de cada vez".

### Opção B — Leaderboard por região
Para cada concelho/município, ranking dos 5 membros por %. "Quem manda em Rio Maior".
- **Prós:** é a vista mais divertida/competitiva, dá para gabarolice no grupo.
- **Contras:** estrutura de dados e UI diferentes da tabela actual — não reaproveita quase nada, é um componente novo de raiz. Mais caro.

### Opção C — Mapa combinado do clube
Mostrar o que o clube **colectivamente** já cobriu (união dos squares de todos), sem distinguir quem fez o quê.
- **Prós:** simples de calcular (união de geometrias, já sei fazer isto — usei `unary_union` hoje para os outlines).
- **Contras:** perde a informação individual, que acho que é o que realmente querias ("visão de complecionismo... para todos os membros" sugere querer ver cada um, não só o total).

**Recomendação:** A primeiro (rápido, reaproveita tudo), e se sobrar apetite/tempo noutra sessão, B como extra por cima — não são mutuamente exclusivas, A dá a base de dados que B também precisa.

---

## 5. Incertezas a validar antes de construir (spike list, mesmo espírito do plano do pipeline)

1. **Tamanho real de `stats_<atleta>.json` para o Pedro** (PT+ES+DE) — estimar antes de decidir entre "um ficheiro por atleta" vs "tudo num só". DE sozinho já são ~21MB só de geometria (não de stats, mas dá ordem de grandeza).
2. **Quantos squares reais cada membro tem** — se for tudo pequeno (dezenas/centenas), a computação é trivial; só a Xeira/Pedro com mais actividade é que pode pesar.
3. **Confirmar com os membros** se querem os dados deles expostos publicamente no mapa (hoje é só o José a ver-se a ele próprio) — isto é uma decisão de privacidade, não só técnica, vale a pena perguntar antes de publicar.

---

## 6. Estimativa de esforço (grosseira, a confirmar ao construir)

- Backend (classify + agregação por atleta, reaproveitando tudo o que já existe): meio dia.
- Frontend Opção A (selector + lazy fetch): meio dia.
- Marrocos (Pedro) e Alemanha ao nível concelho para o Pedro: já resolvido para DE nesta sessão; Marrocos continua sem nada (ver secção "países em falta" — precisa de fonte tipo Overpass, mais trabalho que GISCO).

Total realista: **~1 dia de trabalho**, mais o tempo de máquina para reclassificar squares dos 4 membros (rápido, não é o gargalo — o gargalo de hoje foi construir os totais da grelha, que não se repete).
