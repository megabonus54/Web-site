
CREATE DATABASE auto_parts_shop;
\c auto_parts_shop;

CREATE TABLE Categories (
    Id SERIAL PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Description TEXT
);


CREATE TABLE Suppliers (
    Id SERIAL PRIMARY KEY,
    Name VARCHAR(200) NOT NULL,
    ContactPerson VARCHAR(100),
    Phone VARCHAR(20),
    Email VARCHAR(100)
);


CREATE TABLE Products (
    Id SERIAL PRIMARY KEY,
    Code VARCHAR(50) UNIQUE NOT NULL,
    Name VARCHAR(200) NOT NULL,
    CategoryId INT REFERENCES Categories(Id) ON DELETE SET NULL,
    SupplierId INT REFERENCES Suppliers(Id) ON DELETE SET NULL,
    Manufacturer VARCHAR(100),
    Price DECIMAL(10,2) NOT NULL CHECK (Price >= 0),
    QuantityInStock INT NOT NULL CHECK (QuantityInStock >= 0),
    Description TEXT,
    ImageUrl VARCHAR(255)
);


CREATE TABLE Clients (
    Id SERIAL PRIMARY KEY,
    FullName VARCHAR(150) NOT NULL,
    Phone VARCHAR(20),
    Email VARCHAR(100) UNIQUE NOT NULL,
    PasswordHash VARCHAR(255) NOT NULL, -- для авторизации
    DeliveryAddress TEXT,
    Role VARCHAR(20) DEFAULT 'client' CHECK (Role IN ('admin', 'manager', 'client'))
);


CREATE TABLE Orders (
    Id SERIAL PRIMARY KEY,
    ClientId INT REFERENCES Clients(Id) ON DELETE CASCADE,
    OrderDate DATE NOT NULL DEFAULT CURRENT_DATE,
    Status VARCHAR(50) DEFAULT 'new' CHECK (Status IN ('new', 'processing', 'shipped', 'completed')),
    TotalPrice DECIMAL(10,2) NOT NULL,
    DeliveryMethod VARCHAR(50),
    PaymentMethod VARCHAR(50)
);


CREATE TABLE OrderItems (
    Id SERIAL PRIMARY KEY,
    OrderId INT REFERENCES Orders(Id) ON DELETE CASCADE,
    ProductId INT REFERENCES Products(Id) ON DELETE RESTRICT,
    Quantity INT NOT NULL CHECK (Quantity > 0),
    Price DECIMAL(10,2) NOT NULL -- цена на момент заказа
);