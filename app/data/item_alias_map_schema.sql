CREATE TABLE item_alias_map (
    alias_name TEXT NOT NULL,
    detail_item_code TEXT NOT NULL,
    PRIMARY KEY (alias_name, detail_item_code),
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
