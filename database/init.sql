-- PostgreSQL: dados mestres (propriedades) + camada consolidada (clima e alertas)
CREATE TABLE IF NOT EXISTS propriedades (
  id SERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  produtor TEXT,
  municipio TEXT NOT NULL,
  uf CHAR(2) NOT NULL DEFAULT 'SP',
  lat DOUBLE PRECISION NOT NULL,
  lon DOUBLE PRECISION NOT NULL,
  cultura TEXT NOT NULL,
  area_ha DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS weather_daily (
  propriedade_id INT REFERENCES propriedades(id) ON DELETE CASCADE,
  data DATE NOT NULL,
  tmax DOUBLE PRECISION,
  tmin DOUBLE PRECISION,
  precip DOUBLE PRECISION,
  et0 DOUBLE PRECISION,
  vento_max DOUBLE PRECISION,
  PRIMARY KEY (propriedade_id, data)
);

CREATE TABLE IF NOT EXISTS alertas (
  id SERIAL PRIMARY KEY,
  propriedade_id INT REFERENCES propriedades(id) ON DELETE CASCADE,
  gerado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  tipo TEXT NOT NULL,
  severidade TEXT NOT NULL,      -- info | media | alta
  data_ref DATE,
  mensagem TEXT NOT NULL,
  acao TEXT
);

CREATE TABLE IF NOT EXISTS risco_propriedade (
  propriedade_id INT PRIMARY KEY REFERENCES propriedades(id) ON DELETE CASCADE,
  score INT NOT NULL,
  nivel TEXT NOT NULL,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  resumo JSONB
);

INSERT INTO propriedades (nome, produtor, municipio, uf, lat, lon, cultura, area_ha) VALUES
 ('Fazenda Boa Vista',   'Família Almeida', 'São João da Boa Vista',   'SP', -21.97, -46.80, 'cafe_arabica',   120),
 ('Sítio Pinhal',        'Carlos Mendes',   'Espírito Santo do Pinhal','SP', -22.19, -46.74, 'cafe_arabica',    45),
 ('Fazenda Três Marias', 'Coop. Mogiana',   'Mococa',                  'SP', -21.47, -47.00, 'cana_de_acucar',  300),
 ('Sítio Aguaí',         'Ana Ribeiro',     'Aguaí',                   'SP', -22.06, -46.97, 'milho',            80),
 ('Chácara Citrus Sul',  'Paulo Tanaka',    'Poços de Caldas',         'MG', -21.78, -46.56, 'citros',           60);
