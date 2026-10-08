# 🤖 Contexto do Agente: Plataforma de Integrações Multi-Sistemas (V2.2)

Este documento serve como a memória central e o guia arquitetural do projeto. O objetivo da versão 2.2 é consolidar o ecossistema como uma **Plataforma Multi-Integrações**, suportando ERPs e sistemas verticais (varejo, ótica, odontológico) de forma modular, monitorável e idempotente: **Giga Tech**, **Clinicorp** e **PHIBO**.

---

## 📁 Estrutura Atualizada do Projeto

```
├── worker_gigatech/           # 🐍 Automação Giga Tech
│   ├── main.py
│   ├── scraper.py
│   ├── processor.py
│   ├── database.py
│   ├── ranking_exports/       # 📊 Planilhas XLSX exportadas do Ranking de Vendedores
│   └── tmp_downloads/
│
├── worker_clinicorp/          # 🐍 Automação Clinicorp
│   ├── main.py                # Loop principal de clínicas, idempotência e batch inserts
│   ├── scraper.py             # Playwright headless com bypass de data readonly via JS
│   ├── processor.py           # Tratamento de XLS Clinicorp via Pandas (conversão BR -> US)
│   ├── database.py            # Operações de banco isoladas para as tabelas clinicorp_*
│   └── tmp_downloads/
│
├── worker_phibo/              # 🐍 [NOVO] Automação ERP PHIBO (Vendas & Estoque)
│   ├── main.py                # Loop de lojas, CLI (--client-id, --test-offline, --month)
│   ├── scraper.py             # Playwright headless com detecção de janela de horário e download CSV
│   ├── processor.py           # Parsing de CSV com formatação brasileira e separação cliente/telefone
│   ├── database.py            # Operações de banco isoladas para as tabelas phibo_*
│   └── tmp_downloads/
│
├── web/                       # 🌐 Dashboard Administrativo (Next.js 15)
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/
│   │   │   │   ├── page.tsx   # Portal central de seleção de automações
│   │   │   │   └── [system]/  # Rotas dinâmicas do ERP selecionado (Overview, Clientes, Logs)
│   │   │   └── login/
│   │   ├── components/        # Componentes adaptados para ERPs dinâmicos
│   │   └── utils/
│   │       ├── systems.ts     # Configuração e mapeamento estático de ERPs integrados
│   │       └── kestra.ts      # Integração com a API de execuções do Kestra por sistema
│   └── package.json
│
├── gigatech_orchestrator.yaml # ⚙️ Orquestração Kestra da Giga Tech
├── clinicorp_orchestrator.yaml# ⚙️ Orquestração Kestra da Clinicorp
├── phibo_orchestrator.yaml    # ⚙️ [NOVO] Orquestração Kestra do PHIBO
├── requirements.txt           # Dependências do ambiente Python
└── agent.md                   # Este arquivo (memória do agente)
```

---

## 🗄️ Modelagem de Banco de Dados (Supabase)

Todas as tabelas adotam prefixos do respectivo sistema e possuem **Row Level Security (RLS) habilitado** com políticas que autorizam acessos do usuário logado (`authenticated`).

### Integração Giga Tech
* **`gigatech_clientes_config`**: Credenciais de acesso de cada cliente.
* **`gigatech_vendas`**, **`gigatech_vendedores`**, **`gigatech_clientes_novos`**, **`gigatech_estoque`**, **`gigatech_fechamento_caixa`**: Dados tratados.
* **`gigatech_ranking_vendedores`**: Ranking de vendedores com P.A. (Peças por Atendimento), quantidade de vendas, itens, valor total e ticket médio por vendedor e data (`data_venda`).

### Integração Clinicorp
* **`clinicorp_clientes_config`**: Credenciais da clínica (`id`, `nome_loja`, `email_login_clinicorp`, `senha_login_clinicorp`, `ativo`).
* **`clinicorp_faturamento_profissional`**: Faturamento consolidado bruto de cada dentista/profissional.
* **`clinicorp_orcamentos`**: Listagem de propostas e orçamentos do período.
* **`clinicorp_primeiras_consultas`**: Agendamentos de pacientes de primeira avaliação.
* **`clinicorp_agendamentos_geral`**: Todos os agendamentos da clínica para taxas de comparecimento.
* **`clinicorp_procedimentos_executados`**: Procedimentos executados no período por paciente, com profissional, região e valor.

### Integração PHIBO
* **`phibo_clientes_config`**: Credenciais da loja (`id`, `nome_loja`, `email_login_phibo`, `senha_login_phibo`, `ativo`).
* **`phibo_vendas`**: Vendas detalhadas do período com colunas:
  * `cliente_id`, `origem`, `data_venda`, `hora_venda`, `cliente_nome`, `cliente_telefone`, `cliente_completo`, `vendedor`, `quantidade`, `sub_total`, `desconto`, `trocas`, `cashback`, `frete`, `valor_total`.

*Políticas de RLS:* Adicionadas políticas `clinicorp_*_select`, `_insert`, `_update`, `_delete` para que a API do Next.js e relatórios manipulem e exibam as informações com segurança.

---

## 🐍 Implementação do Worker Clinicorp

O fluxo da Clinicorp foi modularizado de forma idêntica à Giga Tech, garantindo o padrão do projeto:
1. **Playwright Headless & Bypass de Campos Readonly:** 
   * Os inputs de data da Clinicorp (`id=From`, `id=To`, `id=from`, `id=to`, `id=periodFrom`, `id=periodTo`) são configurados como `readonly` no navegador.
   * O `scraper.py` contorna isso executando uma injeção de script via JavaScript (`page.evaluate`) para remover o atributo `readonly`, escrever o valor no formato `dd/mm/yyyy` e disparar os eventos `input` e `change` da DOM para que o React da Clinicorp registre a mudança.
2. **Processamento com Pandas:**
   * Remove linhas acumuladoras de "Valor Total" das planilhas para evitar duplicar somas.
   * Converte strings monetárias no padrão BR (ex: "2.050,00") para floats corretos de banco de dados.
   * **Regra de Data do Faturamento:** Como o relatório de faturamento não exporta uma data por linha, salvamos uma coluna `data` correspondente ao dia 01 do mês de início do filtro selecionado (ex: filtro de `01/06/2026` a `21/06/2026` salva com a data `2026-06-01`).
3. **Idempotência Operacional:** O método `clean_period_data` limpa os dados existentes do cliente e período selecionados no Supabase antes de realizar a inserção em lote (`batch_insert`), prevenindo duplicidades em caso de reexecuções retroativas.

---

## 🐍 Implementação do Worker PHIBO

O fluxo do PHIBO segue o mesmo padrão modular dos demais robôs:
1. **Regra Crítica de Janela Operacional (Horários de Restrição):**
   * O sistema PHIBO (`sistema.phibo.com.br`) bloqueia a exportação de relatórios durante a maior parte do horário comercial com um modal amarelo: *"Esta funcionalidade está desabilitada no momento para garantir o melhor desempenho do sistema..."*.
   * **Janelas permitidas em dias úteis:** Entre **08:00 e 10:10** da manhã e após as **19:10** da noite.
   * O `scraper.py` monitora esse pop-up e lança a exceção `PhiboWindowRestrictionError` com aviso claro para os logs.
2. **Download e Navegação Playwright (Seleção Dinâmica de Período):**
   * Login autenticado com email/senha cadastrados em `phibo_clientes_config`.
   * Acesso à tela *"Relação de vendas"* e seleção da aba *"Mês da Venda"*.
   * **Suporte a Mês Anterior:** O seletor de período do PHIBO utiliza componentes PrimeNG (`p-select`). O scraper detecta se o mês solicitado é o mês anterior (ex: `--month 9` ou fechamento mensal) e aciona automaticamente a opção *"Mês anterior"*, permitindo a extração do mês fechado completo com apenas um clique.
   * Aciona o botão *"Exportar"* e aguarda a conclusão do download do arquivo `relacaoVendasMes.csv`.
3. **Processamento do CSV:**
   * Trata delimitadores (`;` ou `,`) e codificações (`utf-8-sig`, `utf-8`, `latin1`).
   * Higienização de moeda brasileira (`R$`, separador de milhar e decimal).
   * Separação inteligente de cliente e telefone quando presentes na mesma célula (ex: `(88) 99999-9999 - NOME CLIENTE`).
4. **Idempotência Mensal:**
   * O método `clean_vendas_mes` deleta todas as vendas do cliente no intervalo do dia 1 ao último dia do mês corrente antes de fazer o `batch_insert`.

---

## ⚙️ Orquestração Kestra

* O container roda a automação utilizando a imagem oficial do Playwright: `mcr.microsoft.com/playwright/python:v1.44.0-jammy`.
* O script recebe parâmetros via variáveis de ambiente (`KESTRA_CLIENTE_ID`, `KESTRA_DATA_INICIAL`, `KESTRA_DATA_FINAL`) injetados pelo Kestra.
* Se os parâmetros de data estiverem em branco (ex: execução por agendador horário), o worker adota D-0 (hoje) por padrão.
* As credenciais do Supabase (`SUPABASE_URL` e `SUPABASE_KEY`) são injetadas a partir da KV Store global do Kestra, sendo compartilhadas entre os fluxos.

---

## 🌐 Interface Web (Next.js 15)

O dashboard administrativo foi totalmente genérico para atuar como uma plataforma unificada de monitoramento de robôs.

### 1. Portal de Entrada (`/dashboard`)
* Tela inicial premium sem barras de navegação específicas, contendo um grid centralizado de cartões interativos para cada sistema.
* Exibe dinamicamente a contagem de clientes ativos cadastrados no Supabase para cada integração.
* Clicar no sistema redireciona para a respectiva rota dinâmica.

### 2. Rotas Dinâmicas (`/dashboard/[system]`)
* O layout de rotas dinâmicas renderiza o `TopNavbar` com um seletor dropdown (combobox) permitindo alternar de ERP instantaneamente.
* **Overview Desacoplada:** Os cards analíticos do dashboard foram dissociados das tabelas de dados específicos do ERP. Eles exibem estatísticas operacionais obtidas da API do Kestra para o respectivo fluxo:
  * **Clientes Ativos** (puxado do Supabase).
  * **Total de Execuções** (Kestra).
  * **Duração Média das Execuções** (calculada das execuções concluídas).
  * **Taxa de Sucesso** (porcentagem de execuções finalizadas com status `SUCCESS`).
* **CRUD e Logs Dinâmicos:** As telas de listagem de credenciais e visualização de terminal de logs utilizam o mapeamento do `systems.ts` para carregar as tabelas e disparar os webhooks adequados de cada fluxo.

### 3. Registro Centralizado de Configurações (`web/src/utils/systems.ts`)
Facilita a adição de futuras automações ao mapear estaticamente as configurações de cada sistema em um objeto `SYSTEMS`. Para integrar um novo ERP, basta adicionar o ID, nomes de tabelas/colunas de login, chaves do Kestra e ícone correspondente.
