######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductService
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from service import app
from service.common import status
from service.models import db, init_db, Product
from tests.factories import ProductFactory
from urllib.parse import quote_plus

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
logging.disable(logging.CRITICAL)

# DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///../db/test.db')
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, "Could not create test product"
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products

    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data['message'], 'OK')

    # ----------------------------------------------------------
    # TEST CREATE
    # ----------------------------------------------------------
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        logging.debug("Test Product: %s", test_product.serialize())
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

        #
        # Uncomment this code once READ is implemented
        #

        # # Check that the location header was correct
        # response = self.client.get(location)
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        # new_product = response.get_json()
        # self.assertEqual(new_product["name"], test_product.name)
        # self.assertEqual(new_product["description"], test_product.description)
        # self.assertEqual(Decimal(new_product["price"]), test_product.price)
        # self.assertEqual(new_product["available"], test_product.available)
        # self.assertEqual(new_product["category"], test_product.category.name)

    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        logging.debug("Product no name: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    #
    # ADD YOUR TEST CASES HERE
    #

    def test_get_product(self):
        """It should Get a single Product"""
        product = self._create_products(1)[0]
        response = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], product.name)

    def test_get_product_not_found(self):
        """It should not Get a Product that does not exist"""
        response = self.client.get(f"{BASE_URL}/99999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_product(self):
        """It should update a single product"""
        product = self._create_products(1)[0]
        response_prev = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response_prev.status_code, status.HTTP_201_CREATED)
        data_prev = response_prev.get_json()
        data_prev["name"] = "Updated Product"
        self.client.put(
            f"{BASE_URL}/{product.id}",
            json=data_prev
        )
        response = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], "Updated Product")

    def test_delete_product(self):
        """It should delete a single product"""
        # create a list products containing 5 products using the _create_products() method. 
        products = self._create_products(5)
        # call the self.get_product_count() method to retrieve the initial count of products before any deletion
        self.assertEqual(self.get_product_count(), 5)
        # assign the first product from the products list to the variable test_product
        test_product = products[0]
        # send a self.client.delete() request to the BASE_URL with test_product.id
        response = self.client.delete(f"{BASE_URL}/{test_product.id}")
        # assert that the resp.status_code is status.HTTP_204_NO_CONTENT
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # check if the response data is empty
        self.assertEqual(len(response.data), 0)
        # send a self.client.get request to the same endpoint that was deleted to retrieve the deleted product
        response = self.client.get(f"{BASE_URL}/{test_product.id}")
        # assert that the resp.status_code is status.HTTP_404_NOT_FOUND to confirm deletion of the product
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # retrieve the count of products after the deletion operation
        self.assertEqual(self.get_product_count(), 4)

    def test_get_products_list(self):
        """It should Get a list of Products"""
        self._create_products(5)
        # send a self.client.get() request to the BASE_URL
        response = self.client.get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # assert that the resp.status_code is status.HTTP_200_OK
        # get the data from resp.get_json()
        data = response.get_json()
        # assert that the len() of the data is 5 (the number of products you created)
        self.assertEqual(len(data), 5)
        self.assertEqual(self.get_product_count(), 5)

    def test_query_by_name(self):
        """It should Query Products by name"""
        products = self._create_products(5)
        # extract the name of the first product in the products list and assigns it to the variable test_name
        test_name = products[0].name
        # count the number of products in the products list that have the same name as the test_name
        name_count = len([product for product in products if product.name == test_name])
        response = self.client.get(
            BASE_URL, query_string=f"name={quote_plus(test_name)}"
        )
        # assert that response status code is 200, indicating a successful request (HTTP 200 OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # retrieve the JSON data from the response
        data = response.get_json()
        # assert that the length of the data list (i.e., the number of products returned in the response) is equal to name_count
        self.assertEqual(len(data), name_count)
        # use a for loop to iterate through the products in the data list and checks if each product's name matches the test_name
        for product in data:
            self.assertEqual(product["name"], test_name)

    def test_query_by_category(self):
        """It should query the db by category"""
        products = self._create_products(5)
        test_cat = products[0].category
        cat_count = len([prod for prod in products if prod.category == test_cat])
        response = self.client.get(
            BASE_URL, query_string=f"category={quote_plus(test_cat)}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), cat_count)
        for product in data:
            self.assertEqual(product["category"], test_cat.name)

    def test_query_by_availibility(self):
        """It shoudl query the db by availibility"""
        products = self._create_products(10)
        available_products = [product for product in products if product.available is True]
        response = self.client.get(
            BASE_URL, query_string=f"available=true"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data=response.get_json()
        self.assertEqual(len(data), len(available_products))
        for product in data:
            self.assertEqual(product["available"], True)

    ######################################################################
    # Utility functions
    ######################################################################

    def get_product_count(self):
        """save the current number of products"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        # logging.debug("data = %s", data)
        return len(data)
