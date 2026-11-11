-- ============================================================
--  Database: rligabue  (MySQL / MariaDB - compatibile phpMyAdmin)
--  Importazione: phpMyAdmin > Importa > scegli questo file
-- ============================================================
-- Seleziona il database 'rligabue' in phpMyAdmin PRIMA di importare questo file.

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `prodotti`;
DROP TABLE IF EXISTS `categorie`;
DROP TABLE IF EXISTS `dipendenti`;
DROP TABLE IF EXISTS `utenti`;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------- UTENTI ----------
CREATE TABLE `utenti` (
  `id`             INT AUTO_INCREMENT PRIMARY KEY,
  `username`       VARCHAR(50)  NOT NULL UNIQUE,
  `email`          VARCHAR(120) NOT NULL UNIQUE,
  `password_hash`  VARCHAR(255) NOT NULL,            -- mai la password in chiaro
  `ruolo`          ENUM('base','gestore') NOT NULL DEFAULT 'base',
  `attivo`         TINYINT(1)   NOT NULL DEFAULT 0,  -- 1 dopo la mail di conferma
  `creato_il`      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------- CATEGORIE ----------
CREATE TABLE `categorie` (
  `id`    INT AUTO_INCREMENT PRIMARY KEY,
  `nome`  VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ---------- PRODOTTI (con immagine salvata nel DB) ----------
CREATE TABLE `prodotti` (
  `id`              INT AUTO_INCREMENT PRIMARY KEY,
  `nome`            VARCHAR(100) NOT NULL,
  `descrizione`     TEXT,
  `prezzo`          DECIMAL(10,2) NOT NULL,
  `quantita`        INT NOT NULL DEFAULT 0,
  `categoria_id`    INT NULL,
  `immagine`        LONGBLOB NULL,
  `immagine_mime`   VARCHAR(50) NULL,
  `creato_il`       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_prodotti_categoria` FOREIGN KEY (`categoria_id`)
    REFERENCES `categorie`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- DIPENDENTI (mostrati nella pagina Azienda) ----------
CREATE TABLE `dipendenti` (
  `id`        INT AUTO_INCREMENT PRIMARY KEY,
  `nome`      VARCHAR(100) NOT NULL,
  `ruolo`     VARCHAR(100) NOT NULL,
  `bio`       VARCHAR(255) NULL
) ENGINE=InnoDB;

-- ---------- DATI DI ESEMPIO ----------
-- Password:  admin -> Admin123!    |   utente -> Utente123!   (salvate come hash scrypt)
INSERT INTO `utenti` (`username`,`email`,`password_hash`,`ruolo`,`attivo`) VALUES
('admin','admin@nordwave.example','scrypt:32768:8:1$iI5uv01M1AWevftN$325607fc8a65e0d5a3d214319a9997eee508c0498c8a910fa3f85631b0e47fca7b3df6a3056acc8f9414224d998ea74e908fa5927206f3683e29395550fae188','gestore',1),
('utente','utente@nordwave.example','scrypt:32768:8:1$3wHHdCKjhzLoA7qd$34c1e080200df4258ca394f48fd87575652a34d5ef57a6542acb5e717246f43a5335504716d5ed7be084b03b0b05dfcd02d56b1acdba0770fc2998ff7bc12c93','base',1);

INSERT INTO `categorie` (`nome`) VALUES
('Sensori'),('Gateway'),('Software'),('Servizi');

INSERT INTO `prodotti` (`nome`,`descrizione`,`prezzo`,`quantita`,`categoria_id`) VALUES
('Sensore di temperatura T1','Sensore industriale con precisione di 0,1 °C e connessione LoRa.',49.90,120,1),
('Sensore di umidità H2','Misura umidità relativa e punto di rugiada, resistente a polvere e acqua (IP67).',59.00,85,1),
('Sensore di vibrazione V3','Rileva anomalie nei motori e prevede la manutenzione.',129.00,40,1),
('Gateway Edge G10','Raccoglie i dati dei sensori e li invia al cloud in modo cifrato.',349.00,25,2),
('Gateway Edge G20 Pro','Doppia SIM 4G, batteria tampone e 10 porte per sensori.',599.00,12,2),
('Nordwave Cloud Base','Dashboard web per monitorare gli impianti. Licenza annuale.',390.00,999,3),
('Nordwave Cloud Plus','Allarmi via email, report PDF e accesso API. Licenza annuale.',890.00,999,3),
('Installazione e collaudo','Intervento in sede con un tecnico certificato (giornata intera).',480.00,50,4),
('Contratto di assistenza 24/7','Assistenza telefonica e remota con risposta entro 2 ore.',1200.00,50,4);

INSERT INTO `dipendenti` (`nome`,`ruolo`,`bio`) VALUES
('Giulia Ferri','Amministratrice delegata','Ha fondato Nordwave nel 2012 dopo dieci anni in automazione industriale.'),
('Marco Bellini','Responsabile tecnico','Progetta l''hardware dei sensori e coordina il laboratorio.'),
('Sara Conti','Responsabile software','Guida il team che sviluppa la piattaforma cloud.'),
('Luca Moretti','Assistenza clienti','Segue le installazioni e risponde alle richieste urgenti.');
