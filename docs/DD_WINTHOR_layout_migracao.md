Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 1 de 29
1. Diretrizes para geração dos arquivos para migração
 Na geração dos CADASTROS recomenda-se não alterar os códigos (produto, cliente e fornecedor) dos mesmos para evitar problemas na entrega do
SPED. Consulte seu contador antes de modificar os códigos cadastrados.
 Os códigos de cliente 1, 2 e 3 são de USO EXCLUSIVO dos sistemas Winthor e MyMix e nenhum cadastro de cliente poderá ser migrado utilizando tais
códigos. Caso existem clientes que façam uso dos códigos 1, 2 e 3 no sistema legado, os mesmos deverão ser resequenciados. Atentar para a existência
de títulos a receber nos clientes 1, 2 e 3. Caso seja realizado o resequenciamento do cadastro de clientes (tabela PCCLIENT), o mesmo deverá ser
realizado também nos registros de contas a receber (tabela PCPREST).
 Utilizar caracter separador # (cardinal) ou; (ponto e vírgula).
 Incluir caracter separador no final de cada linha (após o conteúdo do último campo do registro).
 Datas no formato DD/MM/YYYY.
 Não incluir espaços no início ou final de um campo para preencher seu conteúdo até o tamanho máximo do campo. Se o campo é de 40 posições, e o
conteúdo de um registro é de apenas 10 posições, colocar no arquivo apenas os 10 caracteres.
 Atenção para os campos obrigatórios que estão marcados como SIM no layout. Todos deverão ser informados no arquivo gerado.
 Campos obrigatórios NÃO deverão ser substituídos por espaços. Colocar separadores em seqüência.
 Valores numéricos devem utilizar o formato 9999.99 (separador decimal deve ser o “ponto”).
 Não utilizar zero a esquerda nos campos numéricos.
 Usar o programa VALIDADORMIGRACAO para inspecionar os arquivos txt’s a serem migrados.
2. Relacionamento entre tabelas
A seguir apresentamos detalhes sobre o relacionamento entre algumas das tabelas a serem migradas para o sistema. Os arquivos textos gerados deverão obedecer
fielmente a esses relacionamentos, sob pena de algumas rotinas do sistema não funcionarem adequadamente após a virada.
Documento de Apoio - DA V 1.3

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 2 de 29
PCPREST
 O conteúdo do campo CODCLI deve ser igual ao PCCLIENT.CODCLI.
 O campo CODCOB deverá conter valores que já estejam cadastrados na tabela PCCOB (cadastro de cobranças). Ex.: CHP, 237, CUST...
 Pode haver várias prestações para uma mesma venda. Nesse caso, incrementar o campo PREST. Abaixo temos um exemplo de uma venda com três
registros no PCPREST.
PCPREST
NUMTRANSVENDA DUPLIC PREST VALOR
789456 123 1 300,00
789456 123 2 300,00
789456 123 3 300,00
 Os campos DTCXMOT e DTFECHA deverão ser preenchidos com a data de emissão.
 O campo OPERACAO deverá ser preenchido com ‘N’ para títulos cuja cobrança seja do tipo boleto bancário (BK, 237, 001). Já para títulos cuja cobrança
seja do tipo “cheque” (CH, CHP), o campo OPERACAO deverá ser preenchido com ‘S’.
 O conteúdo do campo NUMCAR deve ser = 2.
PCTABPR
 Os conteúdos dos campos PTABELA e PVENDA devem ser os mesmos.
 O valor do campo PVENDA corresponde ao preço de partida para o cálculo dos preços PVENDA1, PVENDA2 ... PVENDA7. O valor de PVENDA não
deverá incluir % de frete, nem % financeiro cobrado de acordo com o prazo de pagamento, nem substituição tributária. O próprio sistema fará esses
cálculos de acordo com parâmetros informados. Em síntese, o campo PVENDA não tem frete, não tem financeiro e nem substituição tributária.
Documento de Apoio - DA V 1.3

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 3 de 29
PCPRODUT
• Os campos UNIDADE e UNIDADEMASTER devem ser cadastrados na rotina 204.
• Os campos NBM e CODNCMEX deverão estar cadastrados na rotina 580.
• Os campos CODEPTO e CODSEC deverão estar cadastrados nas rotinas de cadastro.
PCEST
 O valor do custo a ser migrado deve levar em conta o valor do crédito do ICMS, conforme o parâmetros do sistema. Se o parâmetro no sistema estiver
configurado para considerar o crédito de ICMS no cálculo do custo, para um produto que custar 100,00 e entrar com ICMS de 7%, o sistema registrará um
custo de 93,00. Caso o parâmetro no sistema estiver configurado para não considerar o crédito de ICMS no cálculo do custo, para um produto que custar
100,00, o sistema sempre registrará um custo de 100,00, independente do % de crédito que for de direito. Logo, conforme o parâmetro do sistema, o custo
a ser migrado pode ser de 93,00 ou 100,00.
3. Período de movimentação a ser migrado
Segue abaixo uma tabela indicando quais os períodos a serem migrados para as tabelas de movimentação:
Tabela Período
PCPREST Todos os títulos a receber em aberto.
Títulos recebidos: período escolhido pelo cliente (sugestão: 24 meses)
PCLANC Todos os títulos a pagar em aberto.
Títulos pagos: período escolhido pelo cliente (sugestão: 6 meses)
Documento de Apoio - DA V 1.3

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 4 de 29
4. As tabelas que poderão ser migradas para o sistema são as seguintes:
1. Vendedores Cadastro de venededora (RCA's) da empresa, ( PCUSUARI )
2. Praças de entrega Praças de venda e entrega de mercadorias, cidades, bairros, vilas etc. ( PCPRACA )
3. Clientes Empresas (pessoas jurídicas) e pessoas comuns (pessoas físicas) que compram da empresa. ( PCCLIENT )
4. Fornecedores Empresas fornecedoras de mercadorias e serviços para a empresa. ( PCFORNEC )
5. Produtos Mercadorias vendidas ou não que precisam de controle de estoque ou não. ( PCPRODUT )
6. Preços Tabela de preço. ( PCTABPR )
7. Estoque e custos Quantidades físicas e custos de compra das mercadorias de venda ou não. ( PCEST )
8. Contas a pagar Títulos a pagar para fornecedores de mercadorias ou serviços. ( PCLANC )
9. Contas a receber e recebidas Títulos a receber dos clientes incluindo cheques pré-datados. ( PCPREST )
10. NCM Tabela de NCM dos produtos. ( PCNCM )
Tabela complementar ao cadastro de produtos. Permite o cadastro de embagens diferentes e códigos de
11. Embalagens barras distintos para um mesmo produto.
(*) Uso somente no processo de venda por embalagem.( PCEMBALAGEM )
Tabela complementar ao cadastro de clientes. Permite o cadastro de contatos associados ao cliente em
12. Contatos dos Clientes
questão. ( PCCONTATO )
Documento de Apoio - DA V 1.3

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 5 de 29

A seguir o layout dos campos de cada tabela.
4.1.  Vendedores - PCUSUARI
SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1.    CODUSUR  | Sim  | NUMBER(4)     | Código do vendedor  |     |     |     |
| -------------- | ---- | ------------- | ------------------- | --- | --- | --- |
| 2.    NOME     | Sim  | VARCHAR2(40)  | Nome do vendedor    |     |     |     |
| 3.    SENHA    |      | VARCHAR2(10)  |                     |     |     |     |
4.    TIPOVEND   Sim  VARCHAR2(2)  Tipo do vendedor , preencher com (I/ E/ R)  (I) interno  (E) externo  (R) representante.
| 5.    PERCENT     |       | NUMBER(4,2)   | % comissão venda a vista      |     |     |     |
| ----------------- | ----- | ------------- | ----------------------------- | --- | --- | --- |
| 6.    PERCENT2    |       | NUMBER(6,2)   | % comissão venda a prazo      |     |     |     |
| 7.    ENDERECO    |  SIM  | VARCHAR2(40)  |                               |     |     |     |
| 8.    CIDADE      |  SIM  | VARCHAR2(15)  |                               |     |     |     |
| 9.    ESTADO      |  SIM  | VARCHAR2(2)   |                               |     |     |     |
| 10.    CEP        |       | VARCHAR2(9)   |                               |     |     |     |
| 11.    TELEFONE1  |       | VARCHAR2(13)  |                               |     |     |     |
| 12.    TELEFONE2  |       | VARCHAR2(13)  |                               |     |     |     |
| 13.    CPF        |       | VARCHAR2(20)  |                               |     |     |     |
| 14.    CI         |       | VARCHAR2(20)  |  Carteira de Identidade (RG)  |     |     |     |
| 15.    FAX        |       | VARCHAR2(13)  |                               |     |     |     |
| 16.    BIP        |       | VARCHAR2(20)  |                               |     |     |     |
17.    BLOQUEIO     VARCHAR2(1)  O venvedor está bloqueado ou não  (S/N)  S(sim) ou N(não)
18.    DTINICIO   Sim  DATE  Data de inicio do contrato de serviço  No Formato DD/MM/AAAA
19.    DTTERMINO   Sim  DATE  Data de termino do contrato de serviço  Somente se bloqueio for = S , No Formato DD/MM/AAAA

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 6 de 29

20.    MOTIVO   Sim  VARCHAR2(40)  Motivo do bloqueio  Somente se bloqueio for = S
| 21.    DTNASC  |  Sim  | DATE          |     | No Formato DD/MM/AAAA  |     |     |
| -------------- | ----- | ------------- | --- | ---------------------- | --- | --- |
| 22.    FIRMA   |       | VARCHAR2(40)  |     |                        |     |     |
| 23.    CGC     |  Sim  | VARCHAR2(20)  |     |                        |     |     |
| 24.    BAIRRO  |       | VARCHAR2(15)  |     |                        |     |     |
25.    CODSUPERVISOR  Sim  NUMBER(4)   Código do supervisor de vendas
| 26.    EMAIL  |     | VARCHAR2(100)  |     |     |     |     |
| ------------- | --- | -------------- | --- | --- | --- | --- |
27.    Informação apresentada na aba "Informações Adicionais"
OBS1     VARCHAR2(80)   Observação livre  do cadastro de vendedores
28.    Informação apresentada na aba "Informações Adicionais"
OBS2     VARCHAR2(80)   Observação livre  do cadastro de vendedores

4.2.  Praças de entrega - PCPRACA
SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1.    CODPRACA  | Sim  | NUMBER(4)     | Código da Praça  |     |     |     |
| --------------- | ---- | ------------- | ---------------- | --- | --- | --- |
| 2.     PRACA    | Sim  | VARCHAR2(25)  | Nome da praça    |     |     |     |
3.    NUMREGIAO  Sim  NUMBER(4)  Número da região a qual a praça pertence
4.    ROTA  Sim  NUMBER(4)  Número da rota onde a praça está inserida
5.    SEQROTA  Sim  NUMBER(4)  Em que posição da rota a praça está inserida

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 7 de 29

4.3.  Clientes - PCCLIENT
SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1.    CODCLI  | Sim  | NUMBER(6)  | Código do cliente  |     |     |     |
| ------------- | ---- | ---------- | ------------------ | --- | --- | --- |
2.    CLIENTE  Sim  VARCHAR2(60)  razão social do cliente
ENDERCOB  Sim  VARCHAR2(40)  endereço de cobrança do cliente  Exibido no sistema como ENDEREÇO DE COBRANÇA.
| 3.    |     |     |     | Utilizado para emissão de boleto bancário.   |     |     |
| ----- | --- | --- | --- | -------------------------------------------- | --- | --- |
Se nulo preencher com  "O MESMO"
4.    NUMEROCOB    VARCHAR2(6)  Número do endereço de cobrança do cliente
| 5.    BAIRROCOB  |   Sim  | VARCHAR2(40)  | Bairro - cobrança    |     |     |     |
| ---------------- | ------ | ------------- | -------------------- | --- | --- | --- |
| 6.    TELCOB     |        | VARCHAR2(13)  | Telefone - cobrança  |     |     |     |
7.    MUNICCOB    Sim  VARCHAR2(15)  Município - cobrança
| 8.    ESTCOB  |   Sim  | VARCHAR2(2)  | UF - cobrança  |     |     |     |
| ------------- | ------ | ------------ | -------------- | --- | --- | --- |
9.    CEPCOB   Sim   VARCHAR2(9)  Cep - cobrança    Se nulo preencher com o mesmo valor de CEPENT
ENDERENT   Sim  VARCHAR2(40)  Endereço comercial   Exibido no sistema como ENDEREÇO COMERCIAL.
10.
Utilizado como destinatário da nota fiscal.
11.    NUMEROENT    VARCHAR2(6)  Número do endereço de entrega do cliente
| 12.    BAIRROENT  |  Sim    | VARCHAR2(40)  | Bairro - entrega    |     |     |     |
| ----------------- | ------- | ------------- | ------------------- | --- | --- | --- |
| 13.    TELENT     |         | VARCHAR2(13)  | Telefone - entrega  |     |     |     |
14.    MUNICENT    Sim    VARCHAR2(15)  Município - entrega
| 15.    ESTENT  |   Sim    | VARCHAR2(2)   | UF - entrega           |     |     |     |
| -------------- | -------- | ------------- | ---------------------- | --- | --- | --- |
| 16.    CEPENT  |  Sim     | VARCHAR2(9)   | Cep - entrega          |     |     |     |
| 17.    CGCENT  |  Sim     | VARCHAR2(18)  | CGC ou CPF do cliente  |     |     |     |
18.    IEENT   Sim  VARCHAR2(15)  Inscrição estadual do cliente  Se não houver, informar “ISENTO”.
19.    DTULTCOMP     DATE  Data da última compra   No Formato DD/MM/AAAA
20.    CODATV1   Sim  NUMBER(6)  Código do ramo de atividade do cliente  Código da tabela PCATIVI

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 8 de 29
21. BLOQUEIO Sim VARCHAR2(1) Se o cliente está bloquado ou não (S/N) S(sim) ou N(não)
22. CODUSUR1 Sim NUMBER(4) código do vendedor que atende o cliente Código da tabela PCUSUARI
23. CODUSUR2 NUMBER(4) código do segundo vendedor que atende o cliente Código da tabela PCUSUARI
24. FAXCLI VARCHAR2(15) fax do cliente
25. LIMCRED Sim NUMBER(12,2) limite de crédito O valor minimo do limite do credito é de R$ 200,00
OBS VARCHAR2(40) Motivo do bloqueio. Informar somente para clientes Informação exibida no EXTRATO DO CLIENTE, aba
26.
bloqueados FINANCEIRO, campo OBSERVAÇÃO
27. DTPRIMCOMPRA Sim DATE data primeira compra No Formato DD/MM/AAAA
CODCOB Sim VARCHAR2(4) forma de pagamento utilizada pelos clientes onde Código da tabela PCCOB
D=Dinheiro, BK=Boleto, CHV=Cheque Avista, Enviado o valor "D" caso não exista
28. CHP=Cheque Pré-datado, C=Carteira.
Verificar códigos cadastrados na rotina 522 do
sistema
29. DTBLOQ Sim DATE data do bloqueio Só se bloqueio for "S" , No Formato DD/MM/AAAA
30. DTCADASTRO Sim DATE data do cadastro do cliente No Formato DD/MM/AAAA
31. CODPRACA Sim NUMBER(4) praça a que o cliente está ligado Código da tabela PCPRACA
32. FANTASIA Sim VARCHAR2(40) nome fantasia do cliente
OBS2 VARCHAR2(40) Observação adicional. Podem ser observações Informação exibida no EXTRATO DO CLIENTE, aba
33.
comerciais ou financeiras FINANCEIRO, campo OBSERVAÇÃO
34. PONTOREFER VARCHAR2(40) ponto de referência
35. OBSCREDITO VARCHAR2(30) observação sobre o limite de crédito
36. TIPOFJ Sim VARCHAR2(1) Tipo de pessoa (F/J/E) F(física) J(jurídica) E(quando não for F ou J)
37. TELENT1 VARCHAR2(13) telefone adicional
38. EMAIL Sim VARCHAR2(100) email do cliente
CODPLPAG Sim NUMBER(4) Código do prazo de pagamento Código da tabela PCPLPAG
39. Verificar códigos cadastrados na rotina 523 do Enviar o valor 1 caso não exista
sistema
Documento de Apoio - DA V 1.3

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 9 de 29

OBS3     VARCHAR2(60)  Observação adicional. Podem ser observações  Informação exibida no EXTRATO DO CLIENTE, aba
40.
|     |     |     | comerciais ou financeiras  | FINANCEIRO, campo OBSERVAÇÃO  |     |     |
| --- | --- | --- | -------------------------- | ----------------------------- | --- | --- |
OBS4     VARCHAR2(60)  Observação adicional. Podem ser observações  Informação exibida no EXTRATO DO CLIENTE, aba
41.
|     |     |     | comerciais ou financeiras  | FINANCEIRO, campo OBSERVAÇÃO  |     |     |
| --- | --- | --- | -------------------------- | ----------------------------- | --- | --- |
42.    NUMSEQ     NUMBER(10)  sequência de atendimento na praça
| 43.    OBSENTREGA1  |     | VARCHAR2(75)  | Observações sobre entrega  |     |     |     |
| ------------------- | --- | ------------- | -------------------------- | --- | --- | --- |
Dados exibidos na seção "ENDEREÇO COMERCIAL"
| 44.    OBSENTREGA2  |     | VARCHAR2(75)  | Observações sobre entrega  |     |     |     |
| ------------------- | --- | ------------- | -------------------------- | --- | --- | --- |
nos campos "OBSERVAÇÕES"
| 45.    OBSENTREGA3    |     | VARCHAR2(75)  | Observações sobre entrega  |     |     |     |
| --------------------- | --- | ------------- | -------------------------- | --- | --- | --- |
| 46.    OBSGERENCIAL1  |     | VARCHAR2(80)  | Observação gerencial       |     |     |     |
Dados exibidos na seção "OBSERVAÇÕES
47.    OBSGERENCIAL2    VARCHAR2(80)  Observação gerencial  GERENCIAIS"  nos campos "OBSERVAÇÕES
GERENCIAIS"
| 48.    OBSGERENCIAL3  |     | VARCHAR2(80)  | Observação gerencial  |     |     |     |
| --------------------- | --- | ------------- | --------------------- | --- | --- | --- |
OBSERVACAO    VARCHAR2(2000)  Observações adicionais  Dado exibido na seção "OBSERVAÇÕES GERENCIAIS"
49.
no campo "OBSERVAÇÕES ADICIONAIS"
OBS_ADIC    CLOB(4000)  Observações gerais  Dado exibido na seção "OBSERVAÇÕES GERENCIAIS"
50.
no campo "OBSERVAÇÕES GERAIS"
RG    VARCHAR2(20)  N° do documento de identificação pessoal (carteira
51.
de identidade)
52.    CODFILIALNF    VARCHAR2(2)  Filial de faturamento do cliente  Se for apenas uma filial deixar NULO
53.    EMITEDUP  Sim  VARCHAR2(1)  Emite duplicata mercantil para este cliente  (S/N)  S(sim) ou N(não)
54.    CODMUNICIPIO  Sim  NUMBER(10)  Código do município no IBGE  Código de 7 dígitos com base da tabela do IBGE
ENDERCOM  Sim  VARCHAR2(40)  Endereço   Exibido no sistema como ENDEREÇO DE ENTREGA.
| 55.    |     |     |     | Não tem uso prioritário. Se nulo preencher com  "O  |     |     |
| ------ | --- | --- | --- | --------------------------------------------------- | --- | --- |
MESMO"
| 56.    NUMEROCOM  | Não    | VARCHAR2(6)   | Número      |     |     |     |
| ----------------- | ------ | ------------- | ----------- | --- | --- | --- |
| 57.    BAIRROCOM  | Não    | VARCHAR2(40)  | Bairro      |     |     |     |
| 58.    TELCOM     |  Não   | VARCHAR2(13)  | Telefone    |     |     |     |
| 59.    MUNICCOM   | Não    | VARCHAR2(15)  | Município   |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 10 de 29

| 60.    ESTCOM  | Não  | VARCHAR2(2)  | UF   |     |     |     |
| -------------- | ---- | ------------ | ---- | --- | --- | --- |
61.    CEPCOM  Sim  VARCHAR2(9)  Cep    Se nulo preencher com o mesmo valor de CEPENT
62.    CONSUMIDORFINAL  Sim  VARCHAR2(1)  Sinaliza se o cliente é consumidor final ou não  S(sim) ou N(não)
63.    CONTRIBUINTE  Sim  VARCHAR2(1)  Sinaliza se o cliente é contribuinte ou não  S(sim) ou N(não)
64.    CLIENTPROTESTO  Sim  VARCHAR2(1)  Sinaliza se o cliente é passível de ser protestado  S(sim) ou N(não)

4.4.  Fornecedores - PCFORNEC
SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1.    CODFORNEC  | Sim  | NUMBER(6)  | código do fornecedor  |     |     |     |
| ---------------- | ---- | ---------- | --------------------- | --- | --- | --- |
2.    FORNECEDOR  Sim  VARCHAR2(60)  Razão social do fornecedor
3.    REPRES     VARCHAR2(40)  Nome do representante do fornecedor
4.    CONTATO     VARCHAR2(40)  Nome do contato no fornecedor
| 5.    ENDER    |  Sim   | VARCHAR2(40)  | Endereço                   |     |     |     |
| -------------- | ------ | ------------- | -------------------------- | --- | --- | --- |
| 6.    CIDADE   |   Sim  | VARCHAR2(15)  | Cidade                     |     |     |     |
| 7.    ESTADO   |   Sim  | VARCHAR2(2)   | Estado                     |     |     |     |
| 8.    CEP      |  SIm   | VARCHAR2(9)   | Cep                        |     |     |     |
| 9.    TELREP   |        | VARCHAR2(13)  | telefone do representante  |     |     |     |
| 10.    TELFAB  |        | VARCHAR2(13)  | telefone do fabricante     |     |     |     |
| 11.    IE      |  Sim   | VARCHAR2(15)  | Inscrição estadual         |     |     |     |
| 12.    CGC     |  Sim   | VARCHAR2(18)  | CGC do fornecedor          |     |     |     |
| 13.    FAXREP  |        | VARCHAR2(15)  | fax do representante       |     |     |     |
| 14.    FAXFAB  |        | VARCHAR2(15)  | fax do fabricante          |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 11 de 29
15. BAIRRO Sim VARCHAR2(20) Bairro
16. CODCOMPRADOR Sim NUMBER(8) funcionário da empresa que compra do fornecedor Código da tabela PCEMPR
17. CODCONTAB NUMBER(10) conta contábil para fornecedor
18. DTCADASTRO Sim DATE data do cadastro do fornecedor Se não tiver, usar a data da migração , no Formato
DD/MM/AAAA
19. OBS2 VARCHAR2(35) observação
20. EMAIL VARCHAR2(100) Email
21. FANTASIA Sim VARCHAR2(40) nome fantasia do fornecedor
22. SIMPLESNACIONAL Sim VACHAR2(1) Indica optante pelo simples nacional (S/N) S (sim) ou N (não)
23. CODPAIS Sim NUMBER(6,0) Código do país do fornecedor O CODPAIS padrão é 1058, esse é código do Brasil.
24. CODMUNICIPIO Sim NUMBER(10) Código do município no IBGE Código de 7 dígitos com base da tabela do IBGE
25. TIPOPESSOA Sim VARCHAR2(1) Tipo de pessoa (F/J) F(física) ou J(jurídica)
4.5. Produtos - PCPRODUT
SEQ. NOME DO CAMPO OBRIGATÓRIO TIPO DESCRIÇÃO OBSERVAÇÕES
1. CODPROD Sim NUMBER(6) Código do produto
2. DESCRICAO Sim VARCHAR2(40) Descrição do produto
3. EMBALAGEM Sim VARCHAR2(12) Descrição da embalagem de venda do produto
4. UNIDADE Sim VARCHAR2(2) Unidade de venda do produto. Impresso na NF.
5. PESOLIQ Sim NUMBER(7,3) peso líquido da embalagem de venda Maior que 0 ( Zero )
6. PESOBRUTO Sim NUMBER(7,3) peso bruto da embalagem de venda Maior que 0 ( Zero )
7. CODEPTO Sim NUMBER(6) Departamento ao qual o produto pertence Código da tabela PCDEPTO
8. CODSEC Sim NUMBER(6) Seção a qual o produto pertence Código da tabela PCSECAO
Documento de Apoio - DA V 1.3

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 12 de 29

9.    PCOMINT1     NUMBER(6,2)  % comissão para vendedor interno  Não pode ser NULO. Valor mínimo = 0
10.    QTUNIT   Sim  NUMBER(6,2)  Quantidade unitária na embalagem de venda  Não pode ser nulo ou 0. Valor mínimo = 1
11.    PCOMREP1     NUMBER(6,2)  % comissão para representantes   Não pode ser NULO. Valor mínimo = 0
12.    PCOMEXT1     NUMBER(6,2)  % comissão para vendedor externo   Não pode ser NULO. Valor mínimo = 0
13.    CODFORNEC  Sim  NUMBER(6)  Código do fornecedor do produto  Código da tabela PCFORNEC
14.    DTCADASTRO     DATE  Data do cadastro do produto   No Formato DD/MM/AAAA
| 15.    VOLUME       |       | NUMBER(20,8)  |                   |     |     |     |
| ------------------- | ----- | ------------- | ----------------- | --- | --- | --- |
| 16.    CODAUXILIAR  |  Sim  | NUMBER(14)    | Código de barras  |     |     |     |
17.    LASTROPAL   Sim  NUMBER(10,4)  Lastro do Palete.  Se não tiver informar número 1
18.    ALTURAPAL   Sim  NUMBER(10,4)   Altura do Palete.  Se não tiver informar número 1
19.    QTTOTPAL     NUMBER(8,2)   Quantidade Total de paletes.
20.    PRAZOVAL     NUMBER(4)   Validade do Produto.  No Formato DD/MM/AAAA
21.    QTUNITCX   Sim  NUMBER(8,2)  Quantidade de unidades de venda dentro da
embalagem master
22.    MODULO   Sim  NUMBER(2)   Endereçamento do produto.
| 23.    RUA  |  Sim  | NUMBER(4)  | Endereçamento do produto  |     |     |     |
| ----------- | ----- | ---------- | ------------------------- | --- | --- | --- |
24.    NUMERO   Sim  NUMBER(6,2)  Endereçamento do produto
| 25.    APTO           |  Sim  | NUMBER(4)     | Endereçamento do produto  |     |     |     |
| --------------------- | ----- | ------------- | ------------------------- | --- | --- | --- |
| 26.    PERCIPI        |       | NUMBER(10,2)  | % IPI na compra           |     |     |     |
| 27.    UNIDADEMASTER  |  Sim  | VARCHAR2(2)   |                           |     |     |     |
| 28.    PERICM         |       | NUMBER(10,2)  | % ICMS na compra          |     |     |     |
| 29.    PERCDESC       |       | NUMBER(12,4)  | % Desconto na compra      |     |     |     |
30.    PERCST     NUMBER(12,4)  % Substituição Tributária na compra
| 31.    PERCBON    |     | NUMBER(10,2)  | % Bonificação na compra  |     |     |     |
| ----------------- | --- | ------------- | ------------------------ | --- | --- | --- |
| 32.    PERCFRETE  |     | NUMBER(10,2)  | % Frete na compra        |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 13 de 29
33. CLASSIFICFISCAL VARCHAR2(20) Classificação fiscal do produto
34. CODFAB VARCHAR2(30) Código do produto pelo fabricante
35. PISCOFINSRETIDO VARCHAR2(1) Produto tem pis/cofins retido na compra ('S' ou 'N')
36. OBS2 VARCHAR2(2) Fora de Linha e informar ‘FL’ Quando o produto estiver ativo deixar dois espaços em
branco.
37. NBM Sim VARCHAR2(15) Nomenclatura Brasileira de Mercadoria Código NCM do produto
38. CODNCMEX Sim VARCHAR2(20) CódigoNCM + exceção do NCM Código NCM de excessão do produto
39. NATUREZAPRODUTO Sim VARCHAR2(2) Indica a natureza do produto (OT/SS/VC) OT (Outros) ou -SS (Serviços) ou VC (Veículos)
40. UNIDADETRIBUTAVEL SIM VARCHAR2(2) Indica a unidade de venda tributável do produto Caso não tenha unidade diferente utilize a mesma
informação do campo UNIDADE.
4.6. Tabela de preço - PCTABPR
SEQ. NOME DO CAMPO OBRIGATÓRIO TIPO DESCRIÇÃO OBSERVAÇÕES
1. CODPROD Sim NUMBER(6) Código do produto
2. NUMREGIAO Sim NUMBER(4) Número da região onde o produto é vendido
3. PTABELA Sim NUMBER(18,6) Preço de venda do produto
4. PERDESCMAXTAB NUMBER(10,2) % máximo de desconto sobre o preço de tabela
(flexível)
5. MARGEM NUMBER(6,2) Margem de contribuição que se deseja trabalhar com
o produto
6. PTABELA1 Sim NUMBER(18,6)
7. PTABELA2 Sim NUMBER(18,6)
8. PTABELA3 Sim NUMBER(18,6)
9. PTABELA4 Sim NUMBER(18,6)
Documento de Apoio - DA V 1.3

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 14 de 29
10. PTABELA5 Sim NUMBER(18,6)
11. PTABELA6 Sim NUMBER(18,6)
12. PTABELA7 Sim NUMBER(18,6)
13. CODST Sim NUMBER(4) Código da regra de tributação para esse produto Pctribut
nessa região
4.7. Estoque e custos - PCEST
SEQ. NOME DO CAMPO OBRIGATÓRIO TIPO DESCRIÇÃO OBSERVAÇÕES
1. CODFILIAL Sim VARCHAR2(2) Código da filial
2. CODPROD Sim NUMBER(6) Código do produto
3. QTEST Sim NUMBER(22,8) Quantidade fictícia do estoque Essa quantidade no momento da virada será feito um inventario no
estoque ou inserção da quantidade via tabela PCINVENTROT
,onde será finalizado o inventario colcoando as informações
corretas neste campo.
4. DTULTENT Sim DATE Data da última entrada do produto No Formato DD/MM/AAAA
5. QTULTENT NUMBER(16,3) Quantidade da última entrada do produto
6. CUSTOULTENT Sim NUMBER(18,6) Custo da última entrada do produto
7. QTESTGER Sim NUMBER(22,8) Quantidade em estoque (R.)
8. CUSTOCONT Sim NUMBER(18,6) Custo do produto
9. CUSTOREAL Sim NUMBER(18,6) Custo do produto
10. VALORULTENT Sim NUMBER(18,6) Valor pago pelo produto na última entrada
11. QTVENDMES NUMBER(16,3) Quantidade vendida no mês atual
12. QTVENDMES1 NUMBER(16,3) Quantidade vendida no mês anterior
13. QTVENDMES2 NUMBER(16,3) Quantidade vendida nos dois últimos meses
14. QTVENDMES3 NUMBER(16,3) Quantidade vendida nos três últimos meses
Documento de Apoio - DA V 1.3

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 15 de 29
4.8. Contas a pagar - PCLANC
SEQ. NOME DO CAMPO OBRIGATÓRIO TIPO DESCRIÇÃO OBSERVAÇÕES
1. RECNUM Sim NUMBER(8) Identificação do lançamento Gerar sequencial a partir de 1
2. DTLANC Sim DATE Data do lançamento No Formato DD/MM/AAAA
3. CODCONTA Sim NUMBER(10) Código da conta no plano de contas gerencial Tabela PCCONTA
4. CODFORNEC Sim NUMBER(6) Código do fornecedor do título
5. HISTORICO Sim VARCHAR2(40) histórico do título
6. NUMNOTA Sim NUMBER(10) Número do documento a ser pago
7. DUPLIC Sim VARCHAR2(1) Número da parcela referente ao título Número da prestação
8. VALOR Sim NUMBER(12,2) Valor do título
9. DTVENC Sim DATE Data de vencimento do título No Formato DD/MM/AAAA
10. VPAGO NUMBER(12,2) Valor pago Não existe pagto parcial no sistema. Se o cliente possuir
essa situação, deverão se gerados dois registros, um com
o valor quitado e o outro com o restante em aberto.
11. DTPAGTO DATE Data do pagamento
12. CODFILIAL Sim VARCHAR2(2) Código da filial ao qual o título pertence
13. INDICE Sim VARCHAR2(1) Sempre "A"
14. DTEMISSAO Sim DATE Data da emissão do documento a ser pago No Formato DD/MM/AAAA
15. TIPOPARCEIRO Sim VARCHAR2(1) Obrigatório: 'F' para fornecedor 'O' para outros
16. NUMTRANSENT Sim NUMBER(10) Número da transação de entrada Gerar sequencial a partir de 1
Documento de Apoio - DA V 1.3

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 16 de 29

4.9.  Contas a receber - PCPREST
SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1.    CODCLI  | Sim  | NUMBER(6)  | Código do cliente  |     |     |     |
| ------------- | ---- | ---------- | ------------------ | --- | --- | --- |
2.    PREST  Sim  VARCHAR2(2)  Número da parcela do título a receber  Numero da prestação da duplicata
3.    DUPLIC  Sim  NUMBER(10)  Número da NF ao qual o título se refere  É o mesmo número da nota fiscal de origem
4.    VALOR  Sim  NUMBER(10,2)  Valor do título a receber
| 5.    DTVENC  | Sim  | DATE  | Data do vencimento do título  |     |     |     |
| ------------- | ---- | ----- | ----------------------------- | --- | --- | --- |
6.    CODCOB  Sim  VARCHAR2(4)  Código do tipo de cobrança do título  Código da tabela PCCOB
7.    VPAGO     NUMBER(10,2)  Valor pago  Não existe pagto parcial no sistema. Se o cliente possuir
essa situação, deverão se gerados dois registros, um com
o valor quitado e o outro com o restante em aberto.
8.    DTPAG   Sim  DATE  Data do pagamento   No Formato DD/MM/AAAA
9.    DTEMISSAO  Sim  DATE  Data de emissão do título a receber
| 10.    OPERACAO   |      | VARCHAR2(1)  |                   | Sempre "S"  |     |     |
| ----------------- | ---- | ------------ | ----------------- | ----------- | --- | --- |
| 11.    CODFILIAL  | Sim  | VARCHAR2(2)  | Código da filial  |             |     |     |
| 12.    STATUS     | Sim  | VARCHAR2(1)  |                   | Sempre "A"  |     |     |
| 13.    CODUSUR    | Sim  | NUMBER(4)    | Código do RCA     |             |     |     |
14.    NUMBANCO     NUMBER(4)  Número do banco do cheque de pagamento desse
título
15.    NUMAGENCIA     NUMBER(4)  Número da agência do cheque do pagamento desse
título
16.    NUMCHEQUE     NUMBER(8)  Número do cheque do pagamento desse título
17.    NUMCAR     NUMBER(6)  Número do carregamento ao qual o título pertence  Preencher com 2 – carga para títulos migrados
18.    DTFECHA   Sim  DATE  Data de fechamento do carregamento ao qual esse  Preencher com a data de emissão  , no Formato
|     |     |     | título pertence  | DD/MM/AAAA  |     |     |
| --- | --- | --- | ---------------- | ----------- | --- | --- |

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 17 de 29
19. NOSSONUMBCO VARCHAR2(30) Nosso número que é impresso no boleto Caso seja informado o NOSSONUMBCO solicitamos
separar o numeral com um hífen (-). Ex: 12345678-9
20. OBS VARCHAR2(20) observações gerais
21. DTVENCORIG Sim DATE Data de vencimento original No Formato DD/MM/AAAA
22. NUMTRANSVENDA Sim NUMBER(10) Número da transação de venda Gerar sequencial a partir de 1
23. VALORORIG NUMBER(12,2) Usar o mesmo conteúdo do campo VALOR
24. CODCOBORIG VARCHAR2(4) Usar o mesmo conteúdo do campo CODCOB
25. OBS2 VARCHAR2(60) observações gerais
26. DTSAIDA Sim DATE Se não tiver usar DTEMISSAO , no Formato
DD/MM/AAAA
27. CODSUPERVISOR Sim NUMBER(8) Código do supervisor RCA
Documento de Apoio - DA V 1.3

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 18 de 29

4.10.  NCM - PCNCM
SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1.    CODNCM     | Sim  | VARCHAR2(15)   | Código NCM        |     |     |     |
| ---------------- | ---- | -------------- | ----------------- | --- | --- | --- |
| 2.    DESCRIÇÃO  | Sim  | VARCHAR2(500)  | Descrição do NCM  |     |     |     |
| 3.    CAPITULO   | Sim  | NUMBER(2)      | Capítulo          |     |     |     |
| 4.    CODEX      | Não  | NUMBER(4)      | Código Exceção    |     |     |     |
5.    DTINCLUSAO  Não  DATE(7)  Data Inclusão  Formato DD/MM/AAAA
6.    DTEXCLUSAO  Não  DATE(7)  Data Exclusão  Formato DD/MM/AAAA
7.    CODUSURINCLUSAO  Não  NUMBER(8)  Usuário do cadastro
8.    CODUSUREXCLUSAO  Não  NUMBER(8)  Usuário da Exclusão
9.    CODNCMEX  Sim  NUMBER(20)  Código de exceção  Código do NCM + . (ponto)

4.11.  Embalagens de Venda - PCEMBALAGEM

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 19 de 29

SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1  CODAUXILIAR  | Sim  | NUMBER (14)  | Código de barras   |     |     |     |
| --------------- | ---- | ------------ | ------------------ | --- | --- | --- |
| 2  CODPROD      | Sim  | NUMBER (6)   | Código do produto  |     |     |     |
3  EMBALAGEM  Sim  VARCHAR2 (12)  Descrição da embalagem de venda do produto
4  UNIDADE  Sim  VARCHAR2 (2)  Unidade de venda do produto. Impresso na nf
Não pode ser nulo ou zero, valor mínimo =
5  QTUNIT  Sim  NUMBER (6,2)  Quantidade unitária na embalagem de venda
1
| 6  PTABELA  | Sim  | NUMBER (10,2)  | Preço futuro do produto  |     |     |     |
| ----------- | ---- | -------------- | ------------------------ | --- | --- | --- |
| 7  PVENDA   | Sim  | NUMBER (10,2)  | Preço atual do produto   |     |     |     |
DATE
8  DTULTALTPTABELA    Data da última alteração do preço de tabela  No Formato DD/MM/AAAA
“DD/MM/YYYY”
DATE
9  DTULTALTPVENDA    Data da última alteração do preço de venda  No Formato DD/MM/AAAA
“DD/MM/YYYY”
| 10  CODFILIAL    | Sim  | VARCHAR2 (2)   | Código da filial      |     |     |     |
| ---------------- | ---- | -------------- | --------------------- | --- | --- | --- |
| 11  PTABELAATAC  |      | NUMBER (12,3)  | Preço futuro atacado  |     |     |     |
| 12  PVENDAATAC   |      | NUMBER (12,3   | Preço atual atacado   |     |     |     |
13  PRECOANTERIORATAC    NUMBER (12,3)  Preço anterior atacado
14  DESCRICAOECF    VARCHAR2(40)  Descrição do produto no cupom fiscal
15  ENVIABALANCA    VARCHAR2(1)  Enviar produto para balança, valores: “s” ou “n”  S(sim) ou N(não)
|                   |     |              | O que enviar para a balança, valores:   |     | D(descrição) ou E(embalagem)  |     |
| ----------------- | --- | ------------ | --------------------------------------- | --- | ----------------------------- | --- |
| 16  EXPORTACAMPO  |     | VARCHAR2(1)  |                                         |     |                               |     |
|                   |     |              | “d” para descricao, “e” pára embalagem  |     | Somente se ENVIABALANCA = S   |     |
Tipo de embalagem, valores:
| 17  TIPOEMBALAGEM  | Sim  | VARCHAR2(1)  |     |     |     |     |
| ------------------ | ---- | ------------ | --- | --- | --- | --- |
“p” para peso, “u” para unidade
Enviar produto para força de vendas, valores:
| 18  ENVIAFV  |     | VARCHAR2(1)  |     |     |     |     |
| ------------ | --- | ------------ | --- | --- | --- | --- |
“s” ou “n”
19  MARGEM    NUMBER(6,2)  % De margem de venda ideal para o varejo
20  MARGEMIDEALATAC    NUMBER(6,2)  % De margem de venda ideal para o atacado
Quantidade mínima do produto pára preço de venda ser
| 21  QTMINIMAATACADO  |     | NUMBER(18,6)  |     |     |     |     |
| -------------------- | --- | ------------- | --- | --- | --- | --- |
considerado atacado

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 20 de 29

| 4.12.  Contatos dos Clientes - PCCONTATO  |     |     |     |     |     |     |     |
| ----------------------------------------- | --- | --- | --- | --- | --- | --- | --- |

SEQ.  NOME DO CAMPO  OBRIGATÓRIO  TIPO  DESCRIÇÃO  OBSERVAÇÕES
| 1  CODCLI       |     | Sim  | NUMBER(6)     | código do cliente  |     |     |     |
| --------------- | --- | ---- | ------------- | ------------------ | --- | --- | --- |
| 2  NOMECONTATO  |     | Sim  | VARCHAR2(40)  | nome do contato    |     |     |     |
3  TIPOCONTATO  Sim  VARCHAR2(1)  se o contato é sócio ou funcionário (S/F)  S(sócio) ou F(funcionário)
| 4  CGCCPF  |     |     | VARCHAR2(18)  | CGC ou CPF do contato  |     |     |     |
| ---------- | --- | --- | ------------- | ---------------------- | --- | --- | --- |
5  DTNASCIMENTO     DATE  data de nascimento do contato   No Formato DD/MM/AAAA
6  AUTORCH  Sim  VARCHAR2(1)  Autorizado a receber cheque do contato? (S/N)  S(sim) ou N(não)
7  CODCONTATO  Sim  NUMBER (6)  Código do contato  Numero seqüencial independente do código do cliente.
| 8  CARGO  |     |     | VARCHAR2(30)  | Cargo ocupado pelo contato  |     |     |     |
| --------- | --- | --- | ------------- | --------------------------- | --- | --- | --- |
| 9  EMAIL  |     |     | VARCHAR2(50)  | Email do contato            |     |     |     |
10  TELEFONE    VARCHAR2(18)  Telefone comercial do contato
| 11  CELULAR  |     |     | VARCHAR2(18)    | Telefone celular do contato  |     |     |     |
| ------------ | --- | --- | --------------- | ---------------------------- | --- | --- | --- |
| 12  HOBBIE   |     |     | VARCHAR2(50)    | Lazer do contato             |     |     |     |
| 13  OBS      |     |     | VARCHAR2(1000)  | Observação                   |     |     |     |

|     |     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- |

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 21 de 29
SPED PIS/COFINS
 As orientações constantes desta seção do arquivo são para uso exclusivo em caso de migração das informações para geração do SPED PIS/COFINS;
 Sua utilização deve ser primeiramente discutida com o Consultor de Implantação da PC Sistemas para estudo de viabilidade;
5. Diretrizes para geração dos arquivos para migração
 Arquivo no formato texto, codificado em ASCII - ISO 8859-1 (Latin-1), não sendo aceitos campos compactados (packed decimal), zonados, binários, ponto
flutuante (float point), etc., ou quaisquer outras codificações de texto, tais como EBCDIC.
 Arquivo com organização hierárquica, assim definida pela citação do nível hierárquico ao qual pertence cada registro.
 Os registros são sempre iniciados na primeira coluna (posição 1) e têm tamanho variável.
 A linha do arquivo digital deve conter os campos na exata ordem em que estão listados nos respectivos registros.
 Ao início e ao final de cada campo (incluídos o primeiro e o último de cada registro) deve ser inserido o caractere delimitador "|"(Pipe ou Barra Vertical:
caractere 124 da Tabela ASCII).
 O caractere delimitador “|” (Pipe) não deve ser incluído como parte integrante do conteúdo de quaisquer campos numéricos ou alfanuméricos.
 Todos os registros devem conter no final de cada linha do arquivo digital, após o caractere delimitador Pipe acima mencionado, os caracteres "CR"
(Carriage Return) e "LF" (Line Feed) correspondentes a "retorno do carro" e "salto de linha" (CR e LF: caracteres 13 e 10, respectivamente, da Tabela
ASCII).
Exemplo (campos do registro):
TIPO; DATA; CONTA; VALOR
Documento de Apoio - DA V 1.3

Layout para Migração de Dados DA.RPI.010
Sistema de Gestão da Qualidade V 1.9
Página 22 de 29
|C3|12/02/2007|10025|450.00|CRLF
 Na ausência de informação, o campo vazio (campo sem conteúdo; nulo; null) deverá ser iniciado com caractere "|" e imediatamente encerrado com o
mesmo caractere "|" delimitador de campo.
Exemplo (conteúdo do campo)
Campo alfanumérico: José da Silva & Irmãos Ltda -> |José da Silva & Irmãos Ltda|
Campo numérico: 1234,56 -> |1234.56|
Campo numérico ou alfanumérico vazio -> ||
Exemplo (campo vazio no meio da linha)
|123.00||123654788000354|
6. Formato dos campos
 Data (D): a data deverá obedecer ao formato DD/MM/AAAA (dia, mês e ano separados por barras).
 Horário, se for o caso, ao formato HH:MM:SS (horas, minutos e segundos separados por dois pontos).
 Numérico (N): utilizar “.” (ponto) para separar a parte inteira da decimal que deverá ser informada ainda que com zeros (ex.: 999.00); na hipótese de valor
total igual a zero para campo de preenchimento obrigatório, deverá ser informado “0.00”.
 Alfanumérico (X): preenchimento com letras e números.
 Tamanho dos campos: variável, não necessário preencher espaços em branco.
1.
6.1. Registro F01 – Período de migração
Nº Campo Descrição do campo Tipo Tamanho Obs.
Documento de Apoio - DA V 1.3

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 23 de 29

| 01  Registro                   |     | X   | 3   | “F01”         |     |     |     |
| ------------------------------ | --- | --- | --- | ------------- | --- | --- | --- |
| 02  Data inicial               |     | D   | 10  | “DD/MM/YYYY”  |     |     |     |
| 03  Data final                 |     | D   | 10  | “DD/MM/YYYY”  |     |     |     |
| 04  Cód.Unidade Matriz/Filial  |     | X   | 2   |               |     |     |     |

| 6.2.  Registro F10 – Notas fiscais de entrada  |                     |       |                                    |        |     |     |     |
| ---------------------------------------------- | ------------------- | ----- | ---------------------------------- | ------ | --- | --- | --- |
| Nº Campo                                       | Descrição do campo  | Tipo  | Tamanho                            | Obs.   |     |     |     |
| 01  Registro                                   |                     | X     | 3                                  | “F10”  |     |     |     |
| 02  Emissão Própria                            |                     | X     | 1                                  | S/N    |     |     |     |
| 03  Tipo Entrada                               |                     | X     | 1  N – Normal / D – Devolução / I  |        |     |     |     |
– Importação/ O – Outras
| 04  Espécie                        |     | X   | 2                                   | NF/CT/CO      |     |     |     |
| ---------------------------------- | --- | --- | ----------------------------------- | ------------- | --- | --- | --- |
| 05  Série                          |     | X   | 3                                   |               |     |     |     |
| 06  Modelo                         |     | X   | 2                                   |               |     |     |     |
| 07  Dt.Emissao                     |     | D   | 10                                  | “DD/MM/YYYY”  |     |     |     |
| 08  Dt.Saída                       |     | D   | 10                                  | “DD/MM/YYYY”  |     |     |     |
| 09  Núm.Nota                       |     | N   | 10                                  |               |     |     |     |
| 10  Núm. Declaração de Importação  |     | N   | 10  “Informar caso for importação”  |               |     |     |     |
| 12  Cód.Fornecedor                 |     | N   | 6                                   |               |     |     |     |
| 12  Chave NF-e                     |     | N   | 44                                  |               |     |     |     |
| 13  CFOP                           |     | N   | 4  “Informar se não gerar itens”    |               |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 24 de 29

| 14  Vl.Total da Nota        | N   | 12,2                                |     |     |     |     |
| --------------------------- | --- | ----------------------------------- | --- | --- | --- | --- |
| 15  Vl.Desconto             | N   | 12,2                                |     |     |     |     |
| 16  Vl.Base IPI             | N   | 12,2                                |     |     |     |     |
| 17  Vl.IPI                  | N   | 12,2                                |     |     |     |     |
| 18  Vl.Despesa              | N   | 12,2                                |     |     |     |     |
| 19  Vl.Frete                | N   | 12,2                                |     |     |     |     |
| 20  Vl.Base ICMS            | N   | 12,2                                |     |     |     |     |
| 21  % ICMS                  | N   | 7,2  “Informar se não gerar itens”  |     |     |     |     |
| 22  Vl.ICMS                 | N   | 12,2                                |     |     |     |     |
| 23  Vl.Base ICMS ST Retido  | N   | 12,2                                |     |     |     |     |
| 24  Vl.ICMS ST Retido       | N   | 12,2                                |     |     |     |     |
| 25  Vl.Base PIS/COFINS      | N   | 12,2                                |     |     |     |     |
| 26  % PIS                   | N   | 8,4  “Informar se não gerar itens”  |     |     |     |     |
| 27  % COFINS                | N   | 8,4  “Informar se não gerar itens”  |     |     |     |     |
| 28  Vl.PIS                  | N   | 12,2                                |     |     |     |     |
| 29  Vl.COFINS               | N   | 12,2                                |     |     |     |     |
| 30  CST PIS/COFINS          | N   | 2  “Informar se não gerar itens”    |     |     |     |     |
Obs.: Nivel hierárquico: 1

| Documento de Apoio - DA  |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 25 de 29

| 6.3.  Registro F15 – Itens de entrada  |                     |       |                                  |        |     |     |     |
| -------------------------------------- | ------------------- | ----- | -------------------------------- | ------ | --- | --- | --- |
| Nº Campo                               | Descrição do campo  | Tipo  | Tamanho                          | Obs.   |     |     |     |
| 01  Registro                           |                     | X     | 3                                | “F15”  |     |     |     |
| 02  Cód. Produto                       |                     | N     | 6                                |        |     |     |     |
| 03  Núm.Lote                           |                     | X     | 15                               |        |     |     |     |
| 04  CST ICMS                           |                     | N     | 2  “Apenas código da Tabela B –  |        |     |     |     |
Tributação pelo ICMS”
| 05  CFOP                           |     | N   | 4     | < 5000  |     |     |     |
| ---------------------------------- | --- | --- | ----- | ------- | --- | --- | --- |
| 06  Quantidade                     |     | N   | 12,6  |         |     |     |     |
| 07  Vl. bruto unitário do produto  |     | N   | 12,6  |         |     |     |     |
| 08  Vl.Desconto unitário           |     | N   | 12,6  |         |     |     |     |
| 09  CST IPI                        |     | X   | 2     |         |     |     |     |
| 10  Vl.Base IPI unitário           |     | N   | 12,6  |         |     |     |     |
| 11  % IPI                          |     | N   | 7,2   |         |     |     |     |
| 12  Vl. IPI Unitário               |     | N   | 16,6  |         |     |     |     |
| 13  Vl.Despesa Acessória Unitário  |     | N   | 16,6  |         |     |     |     |
| 14  Vl.Frete Unitário              |     | N   | 16,6  |         |     |     |     |
| 15  Vl.Base ICMS Unitário          |     | N   | 16,6  |         |     |     |     |
| 16  % ICMS                         |     | N   | 7,2   |         |     |     |     |
| 17  Vl. Base ICMS ST Unitário      |     | N   | 16,6  |         |     |     |     |
| 18  Vl.ICMS ST Unitário            |     | N   | 16,6  |         |     |     |     |
| 19  Vl.Desconto Suframa Unitário   |     | N   | 16,6  |         |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 26 de 29

| 20  % Redução Base ICMS           |                     | N     | 10,6     |       |     |     |     |
| --------------------------------- | ------------------- | ----- | -------- | ----- | --- | --- | --- |
| 21  CST PIS/COFINS                |                     | N     | 2        |       |     |     |     |
| Nº Campo                          | Descrição do campo  | Tipo  | Tamanho  | Obs.  |     |     |     |
| 22  Vl.Base PIS/COFINS Unitário   |                     | N     | 16,6     |       |     |     |     |
| 23  % PIS                         |                     | N     | 10,4     |       |     |     |     |
| 24  Vl.PIS Unitário               |                     | N     | 16,6     |       |     |     |     |
| 25  % COFINS                      |                     | N     | 10,4     |       |     |     |     |
| 26  Vl.COFINS Unitário            |                     | N     | 16,6     |       |     |     |     |
Obs.: Nivel hierárquico: 2

| 6.4.  Registro F20 – Notas fiscais de saída  |                     |       |                                  |        |     |     |     |
| -------------------------------------------- | ------------------- | ----- | -------------------------------- | ------ | --- | --- | --- |
| Nº Campo                                     | Descrição do campo  | Tipo  | Tamanho                          | Obs.   |     |     |     |
| 01  Registro                                 |                     | X     | 3                                | “F20”  |     |     |     |
| 03  Tipo Saída                               |                     | X     | 1  N – Normal / D – Devolução /  |        |     |     |     |
O – Outras
| 04  Espécie      |     | X   | 2   | NF/CT/CO      |     |     |     |
| ---------------- | --- | --- | --- | ------------- | --- | --- | --- |
| 05  Série        |     | X   | 3   |               |     |     |     |
| 06  Dt.Emissao   |     | D   | 10  | “DD/MM/YYYY”  |     |     |     |
| 07  Dt.Saída     |     | D   | 10  | “DD/MM/YYYY”  |     |     |     |
| 08  Núm.Nota     |     | N   | 10  |               |     |     |     |
| 10  Cód.Cliente  |     | N   | 6   |               |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 27 de 29

| 11  Chave NF-e              |                     | N     | 44                                  |       |     |     |     |
| --------------------------- | ------------------- | ----- | ----------------------------------- | ----- | --- | --- | --- |
| 12  CFOP                    |                     | N     | 4  “Informar se não gerar itens”    |       |     |     |     |
| 13  Vl.Total da Nota        |                     | N     | 12,2                                |       |     |     |     |
| 14  Vl.Desconto             |                     | N     | 12,2                                |       |     |     |     |
| Nº Campo                    | Descrição do campo  | Tipo  | Tamanho                             | Obs.  |     |     |     |
| 15  Vl.Base IPI             |                     | N     | 12,2                                |       |     |     |     |
| 16  Vl.IPI                  |                     | N     | 12,2                                |       |     |     |     |
| 17  Vl.Despesa              |                     | N     | 12,2                                |       |     |     |     |
| 18  Vl.Frete                |                     | N     | 12,2                                |       |     |     |     |
| 19  Vl.Base ICMS            |                     | N     | 12,2                                |       |     |     |     |
| 20  % ICMS                  |                     | N     | 7,2  “Informar se não gerar itens”  |       |     |     |     |
| 21  Vl.ICMS                 |                     | N     | 12,2                                |       |     |     |     |
| 22  Vl.Base ICMS ST Retido  |                     | N     | 12,2                                |       |     |     |     |
| 23  Vl.ICMS ST Retido       |                     | N     | 12,2                                |       |     |     |     |
| 24  Vl.Base PIS/COFINS      |                     | N     | 12,2                                |       |     |     |     |
| 25  % PIS                   |                     | N     | 8,4  “Informar se não gerar itens”  |       |     |     |     |
| 26  % COFINS                |                     | N     | 8,4  “Informar se não gerar itens”  |       |     |     |     |
| 27  Vl.PIS                  |                     | N     | 12,2                                |       |     |     |     |
| 28  Vl.COFINS               |                     | N     | 12,2                                |       |     |     |     |
| 29  CST PIS/COFINS          |                     | N     | 2  “Informar se não gerar itens”    |       |     |     |     |
Obs.: Nivel hierárquico: 1

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 28 de 29

| 6.5.  Registro F25 – Itens de saída  |                     |       |                                  |        |     |     |     |
| ------------------------------------ | ------------------- | ----- | -------------------------------- | ------ | --- | --- | --- |
| Nº Campo                             | Descrição do campo  | Tipo  | Tamanho                          | Obs.   |     |     |     |
| 01  Registro                         |                     | X     | 3                                | “F25”  |     |     |     |
| 02  Cód. Produto                     |                     | N     | 6                                |        |     |     |     |
| 03  Núm.Lote                         |                     | X     | 15                               |        |     |     |     |
| 04  CST ICMS                         |                     | N     | 2  “Apenas código da Tabela B –  |        |     |     |     |
Tributação pelo ICMS”
| 05  CFOP                           |     | N   | 4     | > 5000  |     |     |     |
| ---------------------------------- | --- | --- | ----- | ------- | --- | --- | --- |
| 06  Quantidade                     |     | N   | 12,6  |         |     |     |     |
| 07  Vl. bruto unitário do produto  |     | N   | 12,6  |         |     |     |     |
| 08  Vl.Desconto unitário           |     | N   | 12,6  |         |     |     |     |
| 09  CST IPI                        |     | X   | 2     |         |     |     |     |
| 10  Vl.Base IPI unitário           |     | N   | 12,6  |         |     |     |     |
| 11  % IPI                          |     | N   | 7,2   |         |     |     |     |
| 12  Vl. IPI Unitário               |     | N   | 16,6  |         |     |     |     |
| 13  Vl.Despesa Acessória Unitário  |     | N   | 16,6  |         |     |     |     |
| 14  Vl.Frete Unitário              |     | N   | 16,6  |         |     |     |     |
| 15  Vl.Base ICMS Unitário          |     | N   | 16,6  |         |     |     |     |
| 16  % ICMS                         |     | N   | 7,2   |         |     |     |     |
| 17  Vl. Base ICMS ST Unitário      |     | N   | 16,6  |         |     |     |     |
| 18  Vl.ICMS ST Unitário            |     | N   | 16,6  |         |     |     |     |
| 19  Vl.Desconto Suframa Unitário   |     | N   | 16,6  |         |     |     |     |

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |

                         Layout para Migração de Dados
DA.RPI.010

                                          Sistema de Gestão da Qualidade   V 1.9

Página 29 de 29

| 20  % Redução Base ICMS           |                     | N     | 10,6     |       |     |     |     |
| --------------------------------- | ------------------- | ----- | -------- | ----- | --- | --- | --- |
| 21  CST PIS/COFINS                |                     | N     | 2        |       |     |     |     |
| Nº Campo                          | Descrição do campo  | Tipo  | Tamanho  | Obs.  |     |     |     |
| 22  Vl.Base PIS/COFINS Unitário   |                     | N     | 16,6     |       |     |     |     |
| 23  % PIS                         |                     | N     | 10,4     |       |     |     |     |
| 24  Vl.PIS Unitário               |                     | N     | 16,6     |       |     |     |     |
| 25  % COFINS                      |                     | N     | 10,4     |       |     |     |     |
| 26  Vl.COFINS Unitário            |                     | N     | 16,6     |       |     |     |     |
Obs.: Nivel hierárquico: 2

Os registros deverão ser gerados da seguinte forma:
Exemplo de duas notas fiscais, uma de entrada com três itens e uma de saída com 2 itens.

|F10|...
|F15|...
|F15|...
|F15|...
|F20|...
|F25|...
|F25|...

| Documento de Apoio - DA  |     |     |     |     |     |        | V 1.3  |
| ------------------------ | --- | --- | --- | --- | --- | ------ | ------ |
