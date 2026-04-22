-- ============================================================
-- 模拟真实B端ERP系统的复杂存储过程
-- 基于 ADempiere/iDempiere ERP 的业务逻辑模式
-- ============================================================

-- 1. 订单完成处理 - 涉及多表更新和级联操作
CREATE OR REPLACE PROCEDURE sp_complete_order(
    p_order_id INT,
    p_user_id INT
)
AS
BEGIN
    UPDATE orders
    SET docstatus = 'CO',
        processed = 'Y',
        updatedby = p_user_id,
        updated = CURRENT_TIMESTAMP
    WHERE c_order_id = p_order_id;

    INSERT INTO m_inventory (
        m_inventory_id, ad_client_id, ad_org_id, movementtype,
        movementdate, docstatus, processed
    )
    SELECT
        nextval('m_inventory_seq'),
        o.ad_client_id, o.ad_org_id, 'C',
        o.dateordered, 'DR', 'N'
    FROM orders o
    WHERE o.c_order_id = p_order_id;

    INSERT INTO m_inventoryline (
        m_inventoryline_id, m_inventory_id, m_product_id,
        m_locator_id, qtybook, qtycount, qtyinternaluse
    )
    SELECT
        nextval('m_inventoryline_seq'),
        currval('m_inventory_seq'),
        ol.m_product_id,
        COALESCE(p.m_locator_id, l.m_locator_id),
        COALESCE(si.qtyonhand, 0),
        COALESCE(si.qtyonhand, 0) - ol.qtyordered,
        0
    FROM orderline ol
    JOIN m_product p ON ol.m_product_id = p.m_product_id
    LEFT JOIN m_storage si ON si.m_product_id = ol.m_product_id
    LEFT JOIN m_warehouse w ON w.m_warehouse_id = p.m_warehouse_id
    LEFT JOIN m_locator l ON l.m_warehouse_id = w.m_warehouse_id
    WHERE ol.c_order_id = p_order_id;

    UPDATE m_storage
    SET qtyonhand = qtyonhand - ol.qtyordered,
        updated = CURRENT_TIMESTAMP
    FROM orderline ol
    WHERE m_storage.m_product_id = ol.m_product_id
      AND ol.c_order_id = p_order_id;

    EXEC sp_generate_invoice(p_order_id, p_user_id);

    UPDATE c_bpartner
    SET totalopenbalance = totalopenbalance + o.grandtotal,
        actuallifetimevalue = actuallifetimevalue + o.grandtotal,
        so_creditused = so_creditused + o.grandtotal
    FROM orders o
    WHERE o.c_order_id = p_order_id
      AND c_bpartner.c_bpartner_id = o.c_bpartner_id;

    INSERT INTO fact_acct (
        fact_acct_id, ad_client_id, ad_table_id, record_id,
        account_id, amtacctdr, amtacctcr, c_currency_id,
        dateacct, postingtype
    )
    SELECT
        nextval('fact_acct_seq'),
        o.ad_client_id, 259, p_order_id,
        ev.account_id,
        CASE WHEN ol.linenetamt > 0 THEN ol.linenetamt ELSE 0 END,
        CASE WHEN ol.linenetamt < 0 THEN ABS(ol.linenetamt) ELSE 0 END,
        o.c_currency_id,
        o.dateordered, 'A'
    FROM orders o
    JOIN orderline ol ON ol.c_order_id = o.c_order_id
    JOIN c_elementvalue ev ON ev.c_elementvalue_id = ol.account_id
    WHERE o.c_order_id = p_order_id;
END;
GO

-- 2. 发票生成 - 从订单创建发票并处理税务
CREATE OR REPLACE PROCEDURE sp_generate_invoice(
    p_order_id INT,
    p_user_id INT
)
AS
BEGIN
    INSERT INTO c_invoice (
        c_invoice_id, c_order_id, ad_client_id, ad_org_id,
        c_bpartner_id, c_bpartner_location_id,
        dateinvoiced, dateacct, docstatus, processed,
        totallines, grandtotal, c_currency_id,
        c_paymentterm_id, c_doctype_id, ispaid
    )
    SELECT
        nextval('c_invoice_seq'),
        p_order_id,
        o.ad_client_id, o.ad_org_id,
        o.c_bpartner_id, o.c_bpartner_location_id,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'DR', 'N',
        o.totallines, o.grandtotal, o.c_currency_id,
        o.c_paymentterm_id, o.c_doctype_id, 'N'
    FROM orders o
    WHERE o.c_order_id = p_order_id;

    INSERT INTO c_invoiceline (
        c_invoiceline_id, c_invoice_id, c_orderline_id,
        m_product_id, qtyinvoiced, priceactual,
        linenetamt, taxamt, linetotalamt,
        c_tax_id, c_uom_id
    )
    SELECT
        nextval('c_invoiceline_seq'),
        currval('c_invoice_seq'),
        ol.c_orderline_id,
        ol.m_product_id,
        ol.qtyordered,
        ol.priceactual,
        ol.linenetamt,
        ol.taxamt,
        ol.linenetamt + ol.taxamt,
        ol.c_tax_id,
        ol.c_uom_id
    FROM orderline ol
    WHERE ol.c_order_id = p_order_id;

    INSERT INTO c_invoicetax (
        c_invoicetax_id, c_invoice_id, c_tax_id,
        taxbaseamt, taxamt, istaxincluded
    )
    SELECT
        nextval('c_invoicetax_seq'),
        currval('c_invoice_seq'),
        ol.c_tax_id,
        SUM(ol.linenetamt),
        SUM(ol.taxamt),
        'N'
    FROM orderline ol
    WHERE ol.c_order_id = p_order_id
    GROUP BY ol.c_tax_id;

    UPDATE c_invoice
    SET totallines = (
        SELECT SUM(linenetamt) FROM c_invoiceline
        WHERE c_invoice_id = currval('c_invoice_seq')
    ),
    grandtotal = (
        SELECT SUM(linetotalamt) FROM c_invoiceline
        WHERE c_invoice_id = currval('c_invoice_seq')
    )
    WHERE c_invoice_id = currval('c_invoice_seq');
END;
GO

-- 3. 付款处理 - 处理客户付款和账户更新
CREATE OR REPLACE PROCEDURE sp_process_payment(
    p_payment_id INT,
    p_user_id INT
)
AS
BEGIN
    UPDATE c_payment
    SET docstatus = 'CO',
        processed = 'Y',
        updatedby = p_user_id,
        updated = CURRENT_TIMESTAMP
    WHERE c_payment_id = p_payment_id;

    UPDATE c_invoice
    SET ispaid = CASE
        WHEN c_invoice.grandtotal <= (
            SELECT COALESCE(SUM(pay.payamt), 0)
            FROM c_payment pay
            JOIN c_paymentallocate pa ON pa.c_payment_id = pay.c_payment_id
            WHERE pa.c_invoice_id = c_invoice.c_invoice_id
              AND pay.docstatus = 'CO'
        ) THEN 'Y' ELSE 'N'
    END
    FROM c_paymentallocate pa
    WHERE pa.c_invoice_id = c_invoice.c_invoice_id
      AND pa.c_payment_id = p_payment_id;

    UPDATE c_bpartner
    SET so_creditused = so_creditused - pay.payamt,
        totalopenbalance = totalopenbalance - pay.payamt
    FROM c_payment pay
    WHERE pay.c_payment_id = p_payment_id
      AND c_bpartner.c_bpartner_id = pay.c_bpartner_id;

    INSERT INTO fact_acct (
        fact_acct_id, ad_client_id, ad_table_id, record_id,
        account_id, amtacctdr, amtacctcr, c_currency_id,
        dateacct, postingtype
    )
    SELECT
        nextval('fact_acct_seq'),
        pay.ad_client_id, 335, p_payment_id,
        ev.account_id,
        pay.payamt, 0,
        pay.c_currency_id,
        pay.datetrx, 'A'
    FROM c_payment pay
    JOIN c_bankaccount ba ON ba.c_bankaccount_id = pay.c_bankaccount_id
    JOIN c_bank b ON b.c_bank_id = ba.c_bank_id
    JOIN c_elementvalue ev ON ev.c_elementvalue_id = b.account_id
    WHERE pay.c_payment_id = p_payment_id;

    INSERT INTO fact_acct (
        fact_acct_id, ad_client_id, ad_table_id, record_id,
        account_id, amtacctdr, amtacctcr, c_currency_id,
        dateacct, postingtype
    )
    SELECT
        nextval('fact_acct_seq'),
        pay.ad_client_id, 335, p_payment_id,
        ev.account_id,
        0, pay.payamt,
        pay.c_currency_id,
        pay.datetrx, 'A'
    FROM c_payment pay
    JOIN c_bpartner bp ON bp.c_bpartner_id = pay.c_bpartner_id
    JOIN c_elementvalue ev ON ev.c_elementvalue_id = bp.account_id
    WHERE pay.c_payment_id = p_payment_id;
END;
GO

-- 4. 库存移动 - 仓库间库存转移
CREATE OR REPLACE PROCEDURE sp_move_inventory(
    p_movement_id INT,
    p_user_id INT
)
AS
BEGIN
    UPDATE m_movement
    SET docstatus = 'CO',
        processed = 'Y',
        updatedby = p_user_id,
        updated = CURRENT_TIMESTAMP
    WHERE m_movement_id = p_movement_id;

    UPDATE m_storage
    SET qtyonhand = qtyonhand - ml.movementqty,
        updated = CURRENT_TIMESTAMP
    FROM m_movementline ml
    WHERE m_storage.m_product_id = ml.m_product_id
      AND m_storage.m_locator_id = ml.m_locator_id
      AND ml.m_movement_id = p_movement_id;

    INSERT INTO m_storage (
        m_storage_id, m_product_id, m_locator_id,
        ad_client_id, ad_org_id, qtyonhand
    )
    SELECT
        nextval('m_storage_seq'),
        ml.m_product_id, ml.m_locatorto_id,
        m.ad_client_id, m.ad_org_id, ml.movementqty
    FROM m_movementline ml
    JOIN m_movement m ON m.m_movement_id = ml.m_movement_id
    WHERE ml.m_movement_id = p_movement_id
    ON CONFLICT (m_product_id, m_locator_id) DO UPDATE
    SET qtyonhand = m_storage.qtyonhand + EXCLUDED.qtyonhand;

    INSERT INTO m_transaction (
        m_transaction_id, m_product_id, m_locator_id,
        movementtype, movementqty, movementdate,
        m_movementline_id
    )
    SELECT
        nextval('m_transaction_seq'),
        ml.m_product_id, ml.m_locator_id,
        'M-', ml.movementqty, CURRENT_TIMESTAMP,
        ml.m_movementline_id
    FROM m_movementline ml
    WHERE ml.m_movement_id = p_movement_id;

    INSERT INTO m_transaction (
        m_transaction_id, m_product_id, m_locator_id,
        movementtype, movementqty, movementdate,
        m_movementline_id
    )
    SELECT
        nextval('m_transaction_seq'),
        ml.m_product_id, ml.m_locatorto_id,
        'M+', ml.movementqty, CURRENT_TIMESTAMP,
        ml.m_movementline_id
    FROM m_movementline ml
    WHERE ml.m_movement_id = p_movement_id;
END;
GO

-- 5. 月末结账 - 财务期间关闭处理
CREATE OR REPLACE PROCEDURE sp_close_period(
    p_period_id INT,
    p_user_id INT
)
AS
BEGIN
    UPDATE c_period
    SET periodstatus = 'C',
        periodaction = 'N',
        updatedby = p_user_id,
        updated = CURRENT_TIMESTAMP
    WHERE c_period_id = p_period_id;

    UPDATE c_periodcontrol
    SET periodstatus = 'C',
        periodaction = 'N',
        updatedby = p_user_id,
        updated = CURRENT_TIMESTAMP
    WHERE c_period_id = p_period_id;

    INSERT INTO c_periodcontrol (
        c_periodcontrol_id, c_period_id, ad_client_id,
        docbasetype, periodstatus, periodaction
    )
    SELECT
        nextval('c_periodcontrol_seq'),
        p_period_id,
        p.ad_client_id,
        pc.docbasetype,
        'C', 'N'
    FROM c_period p
    CROSS JOIN c_periodcontrol pc
    WHERE p.c_period_id = p_period_id
      AND pc.c_period_id = p_period_id;

    UPDATE c_elementvalue
    SET currentbalance = (
        SELECT COALESCE(SUM(
            CASE WHEN fa.amtacctdr > 0 THEN fa.amtacctdr ELSE -fa.amtacctcr END
        ), 0)
        FROM fact_acct fa
        JOIN c_period per ON per.c_period_id = p_period_id
        WHERE fa.account_id = c_elementvalue.c_elementvalue_id
          AND fa.dateacct BETWEEN per.startdate AND per.enddate
    ),
    updated = CURRENT_TIMESTAMP,
    updatedby = p_user_id
    WHERE ad_client_id = (
        SELECT ad_client_id FROM c_period WHERE c_period_id = p_period_id
    );

    INSERT INTO t_trial_balance (
        ad_client_id, ad_org_id, c_period_id,
        account_id, amtacctdr, amtacctcr,
        balance_begin, balance_end
    )
    SELECT
        ev.ad_client_id, ev.ad_org_id, p_period_id,
        ev.c_elementvalue_id,
        COALESCE(SUM(fa.amtacctdr), 0),
        COALESCE(SUM(fa.amtacctcr), 0),
        ev.currentbalance - COALESCE(SUM(fa.amtacctdr - fa.amtacctcr), 0),
        ev.currentbalance
    FROM c_elementvalue ev
    LEFT JOIN fact_acct fa ON fa.account_id = ev.c_elementvalue_id
    LEFT JOIN c_period per ON per.c_period_id = p_period_id
        AND fa.dateacct BETWEEN per.startdate AND per.enddate
    WHERE ev.ad_client_id = (
        SELECT ad_client_id FROM c_period WHERE c_period_id = p_period_id
    )
    GROUP BY ev.ad_client_id, ev.ad_org_id, ev.c_elementvalue_id, ev.currentbalance;
END;
GO

-- 6. 产品成本计算 - 计算产品平均成本
CREATE OR REPLACE PROCEDURE sp_update_product_cost(
    p_product_id INT,
    p_client_id INT
)
AS
BEGIN
    UPDATE m_product_costing
    SET currentcostprice = (
        SELECT CASE
            WHEN SUM(movementqty) = 0 THEN currentcostprice
            ELSE SUM(priceactual * movementqty) / SUM(movementqty)
        END
        FROM (
            SELECT ml.movementqty, ol.priceactual
            FROM m_movementline ml
            JOIN orderline ol ON ol.m_product_id = ml.m_product_id
            JOIN orders o ON o.c_order_id = ol.c_order_id
            WHERE ml.m_product_id = p_product_id
              AND o.docstatus = 'CO'
              AND o.dateordered >= CURRENT_DATE - INTERVAL '90 days'
        ) cost_data
    ),
    futurecostprice = (
        SELECT CASE
            WHEN SUM(movementqty) = 0 THEN futurecostprice
            ELSE SUM(priceactual * movementqty) / SUM(movementqty)
        END
        FROM (
            SELECT ml.movementqty, ol.priceactual
            FROM m_movementline ml
            JOIN orderline ol ON ol.m_product_id = ml.m_product_id
            JOIN orders o ON o.c_order_id = ol.c_order_id
            WHERE ml.m_product_id = p_product_id
              AND o.docstatus = 'CO'
        ) cost_data
    ),
    coststandard = (
        SELECT CASE
            WHEN SUM(movementqty) = 0 THEN coststandard
            ELSE SUM(priceactual * movementqty) / SUM(movementqty)
        END
        FROM (
            SELECT ml.movementqty, ol.priceactual
            FROM m_movementline ml
            JOIN orderline ol ON ol.m_product_id = ml.m_product_id
            JOIN orders o ON o.c_order_id = ol.c_order_id
            WHERE ml.m_product_id = p_product_id
              AND o.docstatus = 'CO'
              AND o.dateordered >= CURRENT_DATE - INTERVAL '365 days'
        ) cost_data
    ),
    updated = CURRENT_TIMESTAMP
    WHERE m_product_id = p_product_id
      AND ad_client_id = p_client_id;

    UPDATE m_product
    SET priceactual = (
        SELECT currentcostprice FROM m_product_costing
        WHERE m_product_id = p_product_id AND ad_client_id = p_client_id
    ),
    updated = CURRENT_TIMESTAMP
    WHERE m_product_id = p_product_id;

    INSERT INTO m_costhistory (
        m_costhistory_id, m_product_id, ad_client_id,
        currentcostprice, oldcostprice, created
    )
    SELECT
        nextval('m_costhistory_seq'),
        p_product_id, p_client_id,
        pc.currentcostprice,
        pc.currentcostprice,
        CURRENT_TIMESTAMP
    FROM m_product_costing pc
    WHERE pc.m_product_id = p_product_id
      AND pc.ad_client_id = p_client_id;
END;
GO

-- 7. 客户信用检查 - 评估客户信用额度
CREATE OR REPLACE FUNCTION fn_check_credit(
    p_bpartner_id INT
)
RETURNS TABLE(
    credit_status VARCHAR(20),
    credit_limit NUMERIC,
    credit_used NUMERIC,
    credit_available NUMERIC,
    open_orders NUMERIC,
    open_invoices NUMERIC
)
AS
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN bp.so_creditlimit = 0 THEN 'NO_LIMIT'
            WHEN bp.so_creditused > bp.so_creditlimit * 1.1 THEN 'CREDIT_HOLD'
            WHEN bp.so_creditused > bp.so_creditlimit THEN 'CREDIT_WARNING'
            ELSE 'CREDIT_OK'
        END AS credit_status,
        bp.so_creditlimit AS credit_limit,
        bp.so_creditused AS credit_used,
        bp.so_creditlimit - bp.so_creditused AS credit_available,
        COALESCE((
            SELECT SUM(o.grandtotal)
            FROM orders o
            WHERE o.c_bpartner_id = p_bpartner_id
              AND o.docstatus IN ('DR', 'IP')
        ), 0) AS open_orders,
        COALESCE((
            SELECT SUM(i.grandtotal - i.paidamt)
            FROM c_invoice i
            WHERE i.c_bpartner_id = p_bpartner_id
              AND i.ispaid = 'N'
              AND i.docstatus = 'CO'
        ), 0) AS open_invoices
    FROM c_bpartner bp
    WHERE bp.c_bpartner_id = p_bpartner_id;
END;
GO

-- 8. 价格列表计算 - 批量更新产品价格
CREATE OR REPLACE PROCEDURE sp_update_pricelist(
    p_pricelist_version_id INT,
    p_user_id INT
)
AS
BEGIN
    INSERT INTO m_productprice (
        m_productprice_id, m_pricelist_version_id,
        m_product_id, pricestd, pricelist, pricelimit,
        ad_client_id, ad_org_id
    )
    SELECT
        nextval('m_productprice_seq'),
        p_pricelist_version_id,
        p.m_product_id,
        pc.currentcostprice * (1 + COALESCE(plv.pricelist_stdmargin, 0.3)),
        pc.currentcostprice * (1 + COALESCE(plv.pricelist_listmargin, 0.5)),
        pc.currentcostprice * (1 + COALESCE(plv.pricelist_limitmargin, 0.1)),
        p.ad_client_id, p.ad_org_id
    FROM m_product p
    JOIN m_product_costing pc ON pc.m_product_id = p.m_product_id
    JOIN m_pricelist_version plv ON plv.m_pricelist_version_id = p_pricelist_version_id
    WHERE p.isactive = 'Y'
      AND p.issold = 'Y'
    ON CONFLICT (m_pricelist_version_id, m_product_id) DO UPDATE
    SET pricestd = EXCLUDED.pricestd,
        pricelist = EXCLUDED.pricelist,
        pricelimit = EXCLUDED.pricelimit,
        updated = CURRENT_TIMESTAMP,
        updatedby = p_user_id;

    UPDATE m_pricelist_version
    SET validfrom = CURRENT_DATE,
        updated = CURRENT_TIMESTAMP,
        updatedby = p_user_id
    WHERE m_pricelist_version_id = p_pricelist_version_id;

    UPDATE m_product
    SET priceactual = pp.pricestd,
        pricelist = pp.pricelist,
        pricelimit = pp.pricelimit,
        updated = CURRENT_TIMESTAMP,
        updatedby = p_user_id
    FROM m_productprice pp
    WHERE pp.m_product_id = m_product.m_product_id
      AND pp.m_pricelist_version_id = p_pricelist_version_id;
END;
GO
