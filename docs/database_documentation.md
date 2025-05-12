\*\*Esta é a documentação da base de dados

\*\*Warnings

- O banco de dados é Oracle
- Nunca utilize `;` ao final das queries
- A versão do banco de dados Oracle é 11c, então o código SQL deve ser montado com base nisso

\*\*Info

- Tabelas do banco
  Para obter todas as tabelas do banco é possível simplesmente utilizar a tabela ALL_TABLES para isso

- Informações a respeito de um chassi

* Para obter informações de um chassi específico, basta usar a seguinte query e substituir o {CHASSI_HERE} pelo chassi em questão.

```sql
SELECT
    D.MMC_CHASSI as chassi,
    A.PRODUCTION_ID as PRID,
    B.INV_ITEM_ID as itemID,
    B.DESCR as model,
    C.MMC_COR_MITSUBISHI as color
FROM
    SYSADM.PS_SF_PRDNID_HEADR A,
    SYSADM.PS_MASTER_ITEM_TBL B,
    SYSADM.PS_MMC_COR_RENAVAM C,
    SYSADM.PS_MMC_HIST_CARRO D
WHERE
    B.INV_ITEM_ID = A.INV_ITEM_ID
    AND A.BUSINESS_UNIT = 'IPROC'
    AND B.SETID = C.SETID
    AND SUBSTR (A.CONFIG_CODE, 1, 3) = C.MMC_LOTE_COR_CARRO
    AND A.BUSINESS_UNIT = D.BUSINESS_UNIT
    AND A.PRODUCTION_ID = D.PRODUCTION_ID
    AND D.MMC_CHASSI = '{CHASSI_HERE}'
    -- Pode ser também para múltiplos -> AND D.MMC_CHASSI IN ('{CHASSI_HERE}', '{ANOTHER_CHASSI_HERE}')
```
