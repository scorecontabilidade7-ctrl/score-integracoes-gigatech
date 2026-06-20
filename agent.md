# 🤖 Contexto do Agente: Giga Tech Multi-tenant (V2.0)

Este documento serve como a memória central e o guia arquitetural do projeto. O objetivo principal desta versão 2.0 é transformar a automação em um sistema **Multi-tenant**, rápido (sem uso de Buckets de Storage) e facilmente orquestrável (ex: via Kestra).

---

## ✅ Fase 1: Reestruturação do Banco de Dados (Concluída)

**Objetivo:** Preparar o Supabase (Projeto: `ProjectsGerais`) para armazenar dados de múltiplos clientes na mesma tabela, sem misturá-los, e armazenar as tabelas brutas separadamente (sem a necessidade de realizar o cruzamento/merge prévio via Pandas). Toda a junção final (Venda + Vendedor) ocorrerá via Views/SQL no banco.

### Estrutura Criada

Foram criadas 5 tabelas no projeto `ProjectsGerais`, todas adotando o prefixo `gigatech_`:

#### 1. Tabela Mestra (Multi-tenant)
- **`gigatech_clientes_config`**: Guarda as credenciais e configurações de cada cliente.
  - `id` (UUID, Primary Key)
  - `nome_loja` (Text)
  - `email_login_giga` (Text)
  - `senha_login_giga` (Text)
  - `ativo` (Boolean)

#### 2. Tabelas de Dados Brutos (Staging)
Todas as tabelas abaixo possuem a coluna `cliente_id` como *Foreign Key* vinculada a `gigatech_clientes_config(id)`.

- **`gigatech_vendas`**: Armazena os dados extraídos do Excel de Vendas Detalhadas.
  - Colunas Principais: `data_venda`, `n_cupom`, `produto`, `ean`, `quantidade`, `valor_venda`, `custo`, `margem`.
- **`gigatech_vendedores`**: Armazena os dados do PDF de Vendedores (usado para vincular o vendedor à venda).
  - Colunas Principais: `data_venda`, `n_cupom`, `nome_vendedor`, `nome_cliente`.
- **`gigatech_clientes_novos`**: Armazena os dados do PDF de Clientes cadastrados.
  - Colunas Principais: `nome_cliente`, `data_cadastro`.
- **`gigatech_estoque`**: Armazena os dados do Excel de Custo de Estoque.
  - Colunas Principais: `ean`, `produto`, `quantidade`, `valor_venda`, `custo`.

**Índices de Performance Criados:**
Foram aplicados índices nas colunas `cliente_id` e `data_venda` das tabelas para garantir agilidade nas consultas dos Dashboards quando houver volume massivo de dados.

## ✅ Fase 2 e 3: Unificação, Fim do Bucket e Orquestração Multi-tenant (Concluídas)

**Objetivo:** Eliminar a necessidade de armazenar arquivos no Storage (Bucket) do Supabase e criar o robô orquestrador que puxa os dados do banco e roda para todos os clientes ativos de forma sequencial.

### Estrutura do Código Criada
Todo o código da automação foi isolado na pasta `worker_gigatech/` para não se misturar com a futura interface web:
- **`worker_gigatech/main.py`**: O Orquestrador. Lê os clientes ativos do Supabase, aceita parâmetros de agendadores (`KESTRA_CLIENTE_ID`, etc), controla o loop e deleta arquivos temporários.
- **`worker_gigatech/scraper.py`**: Isola o Playwright. Faz login no sistema web, preenche as datas, baixa os 4 relatórios e salva na pasta `worker_gigatech/tmp_downloads/`.
- **`worker_gigatech/processor.py`**: Isola o tratamento de dados. Usa Pandas/PDFPlumber para ler os arquivos locais, padroniza as colunas e adiciona o `cliente_id` em tempo real.
- **`worker_gigatech/database.py`**: Isola a conexão com o banco. Faz inserções em formato de *Batch* (lotes grandes) para velocidade máxima. Além disso, introduz a função **`clean_period_data()`**, responsável pela **Idempotência**.
  - *Idempotência:* Antes de inserir dados de um período retroativo, o script limpa os dados daquele período específico e daquele cliente nas tabelas para evitar qualquer duplicidade durante re-execuções.
- **Correções do Relatório Giga Tech (Tratamento Múltiplo):** O Pandas foi configurado para prever nomenclaturas diferentes enviadas pelo ERP.
  - Vendas mapeadas com segurança pegando colunas dinâmicas (ex: `EAN`, `Cod.Barra`, `Cód Barra`).
  - Estoque mapeado para absorver nomes como `COD_EAN`, `DES_PRODUTO`, `VAL_VENDA`, e `QTD_ESTOQUE_ATUAL`.
  - Tratamento de colunas recuadas no final da linha (Ex: Coluna `Departamento` em Vendas).

---

## ✅ Fase 4: Integração com Kestra e Conteinerização (Concluída)

**Objetivo:** Preparar o projeto para ser executado no agendador Kestra de forma isolada, em container.

### Arquitetura do Kestra Implementada
- **YAML do Kestra (`gigatech_orchestrator.yaml`)**: Orquestrador master que realiza a clonagem do Github (`git.Clone`) e aciona os workers via `python.Script`.
- **Imagem Oficial do Playwright**: O Kestra utiliza nativamente a imagem `mcr.microsoft.com/playwright/python:v1.44.0-jammy` no container, permitindo que a automação *headless* tenha todos os navegadores embarcados.
- **D-1 Automático (`main.py`)**: O código foi preparado para assumir a data de "Ontem" (D-1) se os parâmetros do cron/kestra vierem vazios, garantindo que o Schedule Diário colete os dados retroativos fechados automaticamente.
- **Variáveis (`KV Store`)**: As credenciais do banco `SUPABASE_URL` e `SUPABASE_KEY` são injetadas no container através de KVs de forma segura.

---

## ✅ Fase 5: Dashboard Web e Gestão de Clientes (Concluída)

**Objetivo:** Criar uma UI web moderna baseada na Identidade Visual da "Score Performance Geral" para que o administrador possa visualizar resultados, gerenciar clientes e disparar processamentos retroativos sob demanda via Webhooks.

### Tecnologias e Implementações (Next.js 15 + Tailwind v4)
- **Design System Premium**: Adotadas as diretrizes visuais da marca, importando Google Fonts assíncronas (Inter global, DM Sans na UI, JetBrains Mono para painéis de dados), garantindo fallback responsivo.
- **Top Navbar Navigation**: Criação de uma barra superior limpa (removendo sidebars complexas) contendo o Logo principal, abas no formato 'pill' e controles de sessão com botão de saída em destaque.
- **Overview (Visão Geral)**: Desenvolvidos os painéis para exibir totalizadores de clientes, vendas, estoque e vendedores.
- **Gestão de Clientes e Credenciais**: 
  - Página de CRUD contendo os clientes ativos e inativos puxados via Server Components diretamente do Supabase (`gigatech_clientes_config`).
  - Utilização de Server Actions seguras e limpas (`actions.ts`) para os modais interativos de Criação e Edição de clientes (Nomes, e-mails, senhas Giga Tech e alteração de status).
- **Disparo de Retroativos (Kestra Webhooks)**: Implementado o modal flutuante `TriggerWebhookDialog` que se comunica via endpoint no lado do cliente. Ao invés do fluxo em lote, o Kestra agora pode ser disparado individualmente enviando o JSON contendo `{ data_inicial, data_final, cliente_id }` do respectivo cliente selecionado na listagem.
- **Histórico de Logs**: Criação da estrutura de tabelas, selos de badges (Rodando, Sucesso, Falha) e alinhamento visual prontos para ingestão de dados das últimas execuções a partir do orquestrador.

---

## ✅ Fase 6: Integração Final de Logs e Painel de Monitoramento (Concluída)

**Objetivo:** Conectar a API do Kestra à interface web para substituir os dados mockados por informações em tempo real das execuções do orquestrador, exibindo logs detalhados e gráficos de performance.

### Tecnologias e Implementações (Logs e Recharts)
- **Integração REST Kestra**: Criada uma camada utilitária em [`web/src/utils/kestra.ts`](file:///c:/Users/LucasVitorino/Documents/Score/score-integracoes-gigatech/web/src/utils/kestra.ts) para se comunicar diretamente com a API do Kestra (`/api/v1/executions/search` e `/api/v1/logs/search`), parseando a URL dinâmica a partir de `KESTRA_WEBHOOK_URL` e utilizando credenciais seguras de Basic Auth via `KESTRA_BASIC_AUTH`.
- **Painel de Controle de Execuções (`LogsTable`)**:
  - Exibe a lista de execuções ordenadas cronologicamente (da mais recente para a mais antiga).
  - Atualiza em tempo real o status de execuções rodando através de polling inteligente no frontend.
- **Console Terminal Interativo**:
  - Drawer lateral expandido (`data-[side=right]:sm:max-w-4xl`) estilizado em formato de console/terminal escuro (`slate-950`).
  - Utiliza fonte monoespaçada (`JetBrains Mono`), evita quebras indesejadas de linha e exibe as mensagens de log coloridas de acordo com o nível (`INFO`, `WARN`, `ERROR`).
  - Polling dinâmico que atualiza as linhas do console em tempo real enquanto a execução estiver ativa.
  - Botão de controle de scroll automático para fácil leitura desde o início.
- **Gráfico de Evolução de Processamento (`ProcessChart`)**:
  - Gráfico de barras interativo construído com Recharts que mostra a duração (em segundos) de cada execução e sua respectiva classificação de status (Sucesso, Falha, Rodando).
  - Ajustes de usabilidade: remoção de borda/outline azul de foco ao clicar no gráfico e cursor transparente para polir a interação visual.

---

## 🚀 Próximas Fases (Planejamento)

1. **Fase 7 (Autenticação Completa):** Plugar a rota de login real com Supabase Auth baseando-se no e-mail master do administrador.

