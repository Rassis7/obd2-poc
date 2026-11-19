# Dicionário do dataset OBD-II

## O que uma linha representa

Cada arquivo original em `sessoes/` corresponde a uma conexão. Cada linha é um objeto JSON independente: pode ser uma resposta, o inventário anunciado por uma central, uma falha ou um evento da sessão. Os sensores são consultados em sequência. Para análise temporal, use a hora de cada leitura; sensores em linhas consecutivas podem ter sido medidos em instantes diferentes.

| Campo | Significado |
|---|---|
| Nome do arquivo | Identificador local da sessão. O arquivo irmão com sufixo `.decodificado.jsonl` representa a mesma sessão. Use uma única versão ao contar amostras. |
| `time` | Hora UTC ISO 8601 do registro pelo Mac, com fração de segundo. É posterior à resposta, sem timestamp interno da ECU. |
| `command` | Consulta enviada. Por exemplo, `0152` significa serviço 01, identificador de parâmetro (PID) hexadecimal 52. |
| `ecu` | Origem da resposta, quando identificável. Exemplo CAN: `7E8`. Separe centrais antes de comparar séries. |
| `raw` | Texto retornado pelo ELM antes da interpretação, sem o prompt final. Pode conter várias tramas e ECUs. Uma resposta completa pode ser repetida nas linhas atribuídas a centrais diferentes. |
| `value`, `unit` | Número e unidade, ou objeto com subcampos e unidade global nula. Valor nulo pode significar resposta sem decodificador ou incompleta. Zero é uma medida válida. |
| `supported` | Lista de identificadores **em decimal** anunciados pela ECU. Exemplo: 82 corresponde a 52 hexadecimal. Vincule ao serviço indicado por `command`. |
| `error` | Erro de consulta, timeout ou ausência de resposta esperada de uma ECU. Pode coexistir com `raw` contendo a resposta de outra ECU. Preserve como dado ausente. |
| `event`, `device` | Início (`start`, com dispositivo), encerramento (`stop`), falha (`error`) ou ciclo de telemetria sem respostas (`ecu_silent`). |

**Como ler uma resposta.** Em CAN, `7E8 03 41 52 66` significa central 7E8, três bytes de conteúdo, resposta positiva ao serviço 01 (41), PID 52 e byte de dados 66 hexadecimal. Para etanol: 102 × 100 / 255 = **40%**. Em mensagens ISO-TP longas, reúna primeira trama e continuações por central e número de sequência antes de aplicar a fórmula. O campo bruto reflete o texto entregue pelo adaptador, não uma captura de todos os quadros da rede CAN.

## Telemetria — serviço 01

Nesta coleta, a ECU 7E8 anunciou e respondeu aos **42 comandos da tabela**. O inventário vem de 0100, 0120, 0140 e 0160. Cada mapa é uma máscara de 32 bits: o bit mais significativo indica base+1 e o menos significativo, base+32 (próximo mapa). Outro veículo pode anunciar um conjunto diferente; o coletor consulta os anunciados mesmo quando só consegue guardar o bruto.

A, B, C… são bytes sem sinal **após** o serviço e PID de resposta. W(X,Y) = 256×X+Y, W = W(A,B), P(X) = 100×X/255 e T(X) = 100×(X−128)/128. Bit 0 é o menos significativo.

| Comando | Significado | Conversão e unidade |
|---|---|---|
| 0101 | Prontidão dos monitores desde a limpeza das falhas | Objeto de máscaras, luz de injeção e contagem de falhas; ver abaixo. |
| 0103 | Estado dos dois sistemas de combustível | A e B como códigos separados. 0 sem indicação, 1 malha aberta por temperatura, 2 fechada com realimentação da sonda, 4 aberta por carga/desaceleração, 8 aberta por falha, 16 fechada com falha. |
| 0104 | Carga calculada do motor | P(A) % |
| 0105 | Temperatura do líquido de arrefecimento | A−40 °C |
| 0106 | Ajuste imediato de combustível, banco 1 | T(A) %; positivo indica acréscimo de combustível. |
| 0107 | Ajuste aprendido de combustível, banco 1 | T(A) % |
| 010A | Pressão manométrica de combustível | 3×A kPa |
| 010B | Pressão absoluta no coletor de admissão | A × limite/255 kPa. Limite padrão 255 kPa; quando 014F informa D > 0, usar 10×D. Nesta ECU o limite é **440 kPa**. |
| 010C | Rotação do motor | W/4 rpm |
| 010D | Velocidade do veículo | A km/h |
| 010E | Avanço de ignição | A/2−64 graus em relação ao ponto morto superior |
| 010F | Temperatura do ar de admissão | A−40 °C |
| 0110 | Vazão mássica de ar (MAF) | W/100 g/s |
| 0111 | Posição absoluta da borboleta | P(A) % |
| 0113 | Sondas de oxigênio presentes | Máscara A. Bits 0–3 indicam sensores 1–4 do banco 1, bits 4–7 os do banco 2. |
| 0114 | Sonda de oxigênio 1, banco 1 | Tensão A/200 V; ajuste associado T(B) % quando B difere de FF hexadecimal. |
| 0115 | Sonda de oxigênio 2, banco 1 | Mesmos dois subcampos do 0114. |
| 011C | Regulamentação OBD declarada | A é código de categoria J1979, armazenado como inteiro. |
| 011F | Tempo desde a partida | W s |
| 0121 | Distância com a luz de injeção acesa | W km |
| 0123 | Pressão manométrica no rail | 10×W kPa |
| 012E | Purga comandada do sistema evaporativo | P(A) % |
| 012F | Nível de combustível indicado | P(A) % da escala do tanque |
| 0130 | Aquecimentos desde a limpeza de falhas | A ciclos |
| 0131 | Distância desde a limpeza de falhas | W km; contador diferente do hodômetro total. |
| 0133 | Pressão barométrica absoluta | A kPa |
| 013C | Temperatura do catalisador, banco 1, sensor 1 | W/10−40 °C |
| 0141 | Estado dos monitores neste ciclo de condução | Máscaras de habilitação e conclusão, descritas abaixo. |
| 0142 | Tensão de alimentação informada pela ECU | W/1000 V |
| 0143 | Carga absoluta do motor | 100×W/255 %; pode exceder 100%. |
| 0144 | Razão de equivalência comandada (lambda) | W/32768, adimensional |
| 0145 | Posição relativa da borboleta | P(A) % |
| 0146 | Temperatura ambiente | A−40 °C |
| 0147 | Posição absoluta da borboleta, canal B | P(A) % |
| 0149 | Posição do pedal do acelerador, canal D | P(A) % |
| 014A | Posição do pedal do acelerador, canal E | P(A) % |
| 014C | Acionamento comandado do atuador da borboleta | P(A) % |
| 014F | Limites de escala declarados pela ECU | A: lambda, B: tensão em V, C: corrente em mA, D×10: pressão absoluta em kPa. São parâmetros de escala; zero pode indicar uso do padrão. |
| 0151 | Tipo de combustível declarado | A é código J1979 (ex.: 1 gasolina). Categoria separada da leitura percentual de etanol. |
| 0152 | Etanol no combustível segundo a ECU | P(A) % |
| 0168 | Temperaturas de admissão por banco e sensor | Bits 0–5 de A validam B–G respectivamente; para cada habilitado, byte−40 °C. Ordem: B1S1…B1S3, B2S1…B2S3. |
| 016D | Pressão comandada, pressão medida e temperatura dos rails | Bits 0–5 de A validam, na ordem: 10×W(B,C), 10×W(D,E), F−40, 10×W(G,H), 10×W(I,J), K−40. Primeiro rail A, depois B; pressões em kPa e temperaturas em °C. |

Para **0101** e **0141**, `compression` é o bit 3 de B (1: ignição por compressão). `basic_mask` guarda B bits 0–2 e `basic_incomplete` guarda B bits 4–6 deslocados para 0–2. A ordem é falha de combustão, sistema de combustível e componentes abrangentes. `monitor_mask` guarda C e `monitor_incomplete` guarda D. O primeiro mapa indica suporte em 0101 e habilitação em 0141; no segundo, bit 1 indica teste incompleto. Os nomes de cada bit dependem da ignição. Somente 0101 usa A: bit 7 para `mil` e bits 0–6 para `dtc_count`. Consulte as tabelas por ignição antes de criar rótulos de falha: teste incompleto não significa teste reprovado. [Detalhes por bit](https://www.dashlogic.com/docs/technical/obdii_pids)

Dois comandos adicionais já têm conversão caso outra central os anuncie: **015C** (óleo do motor, A−40 °C) e **015E** (vazão de combustível, W/20 L/h). O rendimento instantâneo da interface é derivado de velocidade/vazão e não constitui um PID recebido.

## Outros registros que acompanham a telemetria

| Comando | O que o arquivo preserva e como interpretar |
|---|---|
| ATZ, ATI | Reinicialização e identificação textual da versão do adaptador. |
| ATE0, ATL0, ATS1, ATH1, ATSP0 | Respostas à configuração de eco desligado, quebras LF desligadas, espaços ligados, cabeçalhos ligados e protocolo automático. Um OK confirma configuração. |
| ATDPN | Protocolo selecionado. Nesta sessão, A6: escolha automática, ISO 15765-4 CAN de 11 bits a 500 kbit/s. |
| ATRV | Tensão medida pelo adaptador no conector. Exemplo: texto 14.3V → 14,3 V. Ponto de medição diferente de 0142. |
| 02 PID 00 | Quadro congelado de falha nº 0. A resposta positiva começa por 42, PID e nº do quadro. Para sensores equivalentes, use a fórmula do serviço 01 sobre os bytes seguintes. PID 02 identifica o código que originou o quadro. Suporte anunciado não garante quadro armazenado. |
| 03, 07, 0A | Falhas confirmadas, pendentes e permanentes, respectivamente. Respostas 43, 47 e 4A. Em CAN, após o serviço vem a contagem, seguida de pares de bytes. Para cada par: os dois bits superiores escolhem P/C/B/U; os dois seguintes dão o primeiro dígito; os três nibbles restantes dão os demais dígitos hexadecimais. Nesta sessão, as três contagens foram zero. |
| 06 MID | Resultados de autotestes. IDs hex observados: 01/02 sondas do banco 1; 21 catalisador do banco 1; 35 monitor evaporativo; 41/42 aquecedores das sondas; A2–A5 falhas de combustão por cilindro 1–4. No CAN, cada registro de teste contém MID, TID, identificador de unidade/escala e três palavras (resultado, mínimo, máximo). Interpretar sinal, unidade e fator pelo identificador de escala; não comparar palavras brutas de testes diferentes. |
| 09 PID | Informações de identificação anunciadas: 02 VIN, 04 identificador da calibração, 06 número de verificação da calibração, 08 desempenho dos monitores em uso (ignição por centelha), 0A nome da ECU. Reagrupar tramas e interpretar o identificador e a contagem antes dos dados. VIN, nome e calibração usam texto; CVN é binário. |
| 05 | Testes de oxigênio consultados em protocolos legados selecionados. A sessão CAN analisada usou serviço 06. |

O arquivo preserva as respostas desses serviços para análise posterior. A normalização automática desta versão cobre a telemetria do serviço 01; os demais serviços mantêm seu formato bruto e, quando reconhecidos pelo coletor, sua central e inventário. A coleta não pretende enumerar parâmetros proprietários de cada fabricante.

## Usar como dataset

Na pasta do projeto, execute `python3 reprocess.py sessoes/arquivo.jsonl` para aplicar o decodificador ao histórico. Para a sessão original de 19/11/2026 cujo nome começa com `8e077343`, a cópia mantém 5.866 linhas, com 4.996 registros de telemetria decodificados, distribuídos por 42 PIDs. Guarde o original e associe a versão do código ao material derivado para poder repetir a conversão.

Para treinar com séries numéricas, filtre respostas válidas por sessão, central e comando. Expanda objetos como 016D em colunas com unidades próprias. Mantenha as linhas de erro para avaliar lacunas. Antes de compartilhar dados, considere que VIN e identificador Bluetooth podem identificar o veículo ou aparelho.

Referências para os serviços, enumerações e conversões: [tabelas do python-OBD](https://python-obd.readthedocs.io/en/latest/Command%20Tables/), [parâmetros J1979 e cálculos por byte](https://pelican.clutch.engineering/cars/saej1979/parameters), [definições de serviços e parâmetros SAE J1979](https://www.autonerdz.com/yabbfiles/Attachments/1979v3.pdf).
