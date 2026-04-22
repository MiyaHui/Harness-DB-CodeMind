CREATE PROCEDURE sp_order_pay
    @order_id INT,
    @payment_method VARCHAR(50)
AS
BEGIN
    INSERT INTO payment (order_id, amount, payment_method, status, created_at)
    SELECT o.id, o.total_amount, @payment_method, 'PENDING', GETDATE()
    FROM orders o
    WHERE o.id = @order_id;

    UPDATE orders
    SET status = 'PAID', paid_at = GETDATE()
    WHERE id = @order_id;

    EXEC sp_generate_invoice @order_id;

    UPDATE inventory
    SET stock_quantity = stock_quantity - o.quantity
    FROM orders o
    WHERE o.id = @order_id;
END
GO

CREATE PROCEDURE sp_generate_invoice
    @order_id INT
AS
BEGIN
    INSERT INTO invoice (order_id, total_amount, tax_amount, net_amount, status)
    SELECT o.id, o.total_amount, o.total_amount * 0.08, o.total_amount * 1.08, 'GENERATED'
    FROM orders o
    WHERE o.id = @order_id;

    INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, subtotal)
    SELECT i.id, p.name, oi.quantity, oi.unit_price, oi.quantity * oi.unit_price
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    JOIN invoice i ON i.order_id = @order_id
    WHERE oi.order_id = @order_id;

    UPDATE customer_account
    SET total_spent = total_spent + o.total_amount,
        order_count = order_count + 1
    FROM orders o
    WHERE o.id = @order_id
      AND o.customer_id = customer_account.customer_id;
END
GO

CREATE PROCEDURE sp_cancel_order
    @order_id INT
AS
BEGIN
    UPDATE orders
    SET status = 'CANCELLED', cancelled_at = GETDATE()
    WHERE id = @order_id;

    UPDATE inventory
    SET stock_quantity = stock_quantity + oi.quantity
    FROM order_items oi
    WHERE oi.order_id = @order_id;

    UPDATE payment
    SET status = 'REFUNDED'
    WHERE order_id = @order_id;

    UPDATE customer_account
    SET total_spent = total_spent - o.total_amount,
        order_count = order_count - 1
    FROM orders o
    WHERE o.id = @order_id
      AND o.customer_id = customer_account.customer_id;
END
GO

CREATE PROCEDURE sp_monthly_report
    @month INT,
    @year INT
AS
BEGIN
    INSERT INTO monthly_report (month, year, total_revenue, order_count, avg_order_value)
    SELECT @month, @year,
           SUM(o.total_amount),
           COUNT(*),
           AVG(o.total_amount)
    FROM orders o
    WHERE MONTH(o.created_at) = @month
      AND YEAR(o.created_at) = @year
      AND o.status != 'CANCELLED';

    INSERT INTO product_report (month, year, product_id, product_name, quantity_sold, revenue)
    SELECT @month, @year, p.id, p.name,
           SUM(oi.quantity),
           SUM(oi.quantity * oi.unit_price)
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    JOIN orders o ON oi.order_id = o.id
    WHERE MONTH(o.created_at) = @month
      AND YEAR(o.created_at) = @year
      AND o.status != 'CANCELLED'
    GROUP BY p.id, p.name;

    UPDATE report_status
    SET last_generated = GETDATE(),
        status = 'COMPLETED'
    WHERE report_type = 'MONTHLY'
      AND month_param = @month
      AND year_param = @year;
END
GO

CREATE PROCEDURE sp_update_product_price
    @product_id INT,
    @new_price DECIMAL(10,2)
AS
BEGIN
    UPDATE products
    SET price = @new_price,
        updated_at = GETDATE()
    WHERE id = @product_id;

    INSERT INTO price_history (product_id, old_price, new_price, changed_at)
    SELECT @product_id, price, @new_price, GETDATE()
    FROM products
    WHERE id = @product_id;

    UPDATE order_items
    SET unit_price = @new_price
    WHERE product_id = @product_id
      AND order_id IN (SELECT id FROM orders WHERE status = 'PENDING');
END
GO
