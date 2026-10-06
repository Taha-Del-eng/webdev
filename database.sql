-- Run this in SQL Server Management Studio 2022 (New Query -> Execute)
CREATE DATABASE InventoryDB;
GO
USE InventoryDB;
GO

CREATE TABLE Products (
    ProductID INT IDENTITY(1,1) PRIMARY KEY,
    Name      NVARCHAR(100) NOT NULL,
    Category  NVARCHAR(50)  NOT NULL,
    Price     DECIMAL(10,2) NOT NULL,
    Stock     INT           NOT NULL DEFAULT 0,
    Emoji     NVARCHAR(10)  NOT NULL DEFAULT N'📦'
);
GO

INSERT INTO Products (Name, Category, Price, Stock, Emoji) VALUES
(N'Wireless Earbuds Pro',   N'Electronics', 4999,  35, N'🎧'),
(N'Smart Watch Series 5',   N'Electronics', 8999,  12, N'⌚'),
(N'Bluetooth Speaker',      N'Electronics', 3499,  4,  N'🔊'),
(N'Gaming Mouse RGB',       N'Electronics', 2799,  50, N'🖱️'),
(N'Men Running Shoes',      N'Fashion',     5499,  22, N'👟'),
(N'Leather Wallet',         N'Fashion',     1299,  60, N'👛'),
(N'Women Handbag',          N'Fashion',     3999,  3,  N'👜'),
(N'Sunglasses UV400',       N'Fashion',     999,   40, N'🕶️'),
(N'Non-Stick Fry Pan',      N'Home',        1899,  18, N'🍳'),
(N'Table Lamp LED',         N'Home',        1499,  27, N'💡'),
(N'Cotton Bedsheet Set',    N'Home',        2999,  9,  N'🛏️'),
(N'Water Bottle 1L',        N'Home',        599,   100,N'🍶');
GO
