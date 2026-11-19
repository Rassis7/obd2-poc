# Telemetria OBD-II no macOS

Requer Python 3, acesso à internet na primeira execução para instalar Bleak, e as Command Line Tools da Apple (xcode-select --install). Na pasta do projeto execute:

    ./start.sh

Abra http://127.0.0.1:8765 no navegador. O script compila a ponte Bluetooth com os frameworks do macOS. Conecte o ELM327 à tomada OBD-II do carro e ligue a ignição. Clique em **Buscar dispositivos**, permita o Bluetooth nos Ajustes do Sistema se solicitado, selecione o aparelho pelo nome/endereço e clique em **Conectar**. A busca inclui dispositivos clássicos pareados e descobertos, e periféricos BLE anunciando no momento. Selecione a entrada BLE para adaptadores que a oferecem. A coleta BLE usa o serviço FFF0, com FFF1 para respostas e FFF2 para comandos. O Bluetooth clássico usa o serviço serial SPP. Se o pareamento exigir PIN e falhar pela página, pareie pelos Ajustes do Sistema com o PIN da unidade e repita a busca.

O indicador da central muda ao receber uma resposta OBD válida. RPM, velocidade e temperatura dependem do suporte do veículo. Cada sessão cria um JSONL em sessoes/ e a página informa o caminho absoluto. Os registros contêm hora UTC, consulta, resposta textual e, quando identificados, central, valor e unidade. Mapas de suporte aparecem em registros com supported. Tramas longas e respostas não decodificadas permanecem no campo raw. O arquivo pode conter o VIN do veículo.

A coleta serial consulta os parâmetros anunciados em sequência. Uma volta completa pode levar vários segundos. Fechar a aba mantém o processo ativo. Use **Encerrar coleta** para finalizar após a consulta corrente ou Ctrl+C no terminal. Para conferir a cobertura, compare os registros supported de cada modo com os comandos registrados depois de cada mapa (incluindo erros). Uma sessão interrompida antes do primeiro ciclo pode ter inventário parcial.

    python3 -m unittest discover -s tests -v

A dashboard exibe os sensores anunciados pela central: rotação, velocidade, temperatura do líquido de arrefecimento, carga, borboleta, temperaturas do ar e do óleo, tensão da central, vazão e nível de combustível, MAP, MAF e correções de combustível do banco 1. Os novos valores e unidades são registrados no JSONL junto à resposta bruta. O rendimento instantâneo é calculado na página quando velocidade e vazão são positivas e a mesma central informou ambas nos últimos 10 segundos. Em marcha lenta, acompanhe L/h.

Para decodificar as respostas de uma sessão anterior, execute `python3 reprocess.py sessoes/arquivo.jsonl`. O comando cria um arquivo irmão com sufixo `.decodificado.jsonl` e preserva o original.

Consulte o [dicionário do dataset](DADOS-OBD.md) para interpretar os campos do JSONL, fórmulas dos sensores e respostas de diagnóstico.

### Sandbox sem carro

Em um terminal, instale e execute o emulador (dependência apenas do sandbox):

```sh
.build/venv/bin/python -m pip install elmulator==0.3.3
.build/venv/bin/elmulator serve obd_dashboard.scenario.json --port 35000
```

Em outro terminal execute `./start.sh`, abra a dashboard e clique em **Usar sandbox simulado**. A sessão e o arquivo identificam a origem simulada. O sandbox usa TCP local e não valida a comunicação BLE com o adaptador físico.

#### Reproduzir dados de uma sessão gravada

Você pode usar uma coleta anterior como simulado, sem conectar o carro ou o adaptador. Com o servidor iniciado por `./start.sh`, abra a dashboard. Em **Reproduzir sessão gravada**, selecione um arquivo `.jsonl` listado da pasta `sessoes/` e clique em **Reproduzir**. A dashboard mostrará os valores e horários atualizados seguindo a ordem e os intervalos registrados no arquivo. O status indicará **REPRODUÇÃO**; o arquivo original não será alterado e nenhum novo arquivo de coleta será criado. Clique em **Encerrar coleta** para interromper a reprodução. Se acabou de copiar uma sessão para `sessoes/`, clique em **Atualizar lista**.

Isso é diferente do **sandbox simulado** com elmulator descrito acima: a reprodução usa dados reais de uma coleta gravada; o elmulator responde a comandos com um cenário sintético por TCP.
