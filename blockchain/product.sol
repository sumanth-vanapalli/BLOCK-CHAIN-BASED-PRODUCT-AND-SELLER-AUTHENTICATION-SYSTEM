// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ProductVerification {

    struct Product {
        string name;
        string manufacturer;
        string productId;
        bool isRegistered;
    }

    mapping(string => Product) private products;

    // Register product
    function addProduct(
        string memory _name,
        string memory _manufacturer,
        string memory _productId
    ) public {

        require(
            !products[_productId].isRegistered,
            "Product already registered"
        );

        products[_productId] = Product(
            _name,
            _manufacturer,
            _productId,
            true
        );
    }

    // Verify product authenticity
    function verifyProduct(string memory _productId)
        public
        view
        returns (
            string memory,
            string memory,
            bool
        )
    {
        Product memory p = products[_productId];
        return (p.name, p.manufacturer, p.isRegistered);
    }
}
