
DELETE FROM ir_model_data WHERE name like'%unspsc_code_%';
DELETE FROM product_unspsc_code;
DELETE FROM ir_model_data WHERE model='product_unspsc_code';