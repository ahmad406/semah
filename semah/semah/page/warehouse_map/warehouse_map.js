// Warehouse Map - live visual bin grid
// Renders rows of bins color-coded by state, click any bin for full contents.

frappe.pages['warehouse-map'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Warehouse Map'),
		single_column: true,
	});
	wrapper.warehouse_map = new WarehouseMap(page);
};

frappe.pages['warehouse-map'].on_page_show = function (wrapper) {
	if (wrapper.warehouse_map) wrapper.warehouse_map.refresh();
};

class WarehouseMap {
	constructor(page) {
		this.page = page;
		this.warehouse = null;
		this.expiry_days = 30;
		this.highlight_bins = [];
		this.make_toolbar();
		this.make_body();
		this.refresh();
	}

	make_toolbar() {
		var me = this;

		this.warehouse_field = this.page.add_field({
			fieldname: 'warehouse',
			label: __('Warehouse'),
			fieldtype: 'Link',
			options: 'Warehouse',
			change() {
				me.warehouse = this.get_value();
				me.refresh();
			},
		});

		this.search_field = this.page.add_field({
			fieldname: 'item_search',
			label: __('Find Item / Batch'),
			fieldtype: 'Data',
			change() {
				me.do_item_search(this.get_value());
			},
		});

		this.expiry_field = this.page.add_field({
			fieldname: 'expiry_days',
			label: __('Expiry alert (days)'),
			fieldtype: 'Select',
			options: ['15', '30', '60', '90'],
			default: '30',
			change() {
				me.expiry_days = cint(this.get_value()) || 30;
				me.refresh();
			},
		});

		this.page.set_primary_action(__('Refresh'), () => me.refresh(), 'refresh');
	}

	make_body() {
		this.body = $(`
			<div class="wh-map">
				<div class="wh-map-summary row" style="margin: 0 0 12px;"></div>
				<div class="wh-map-legend" style="display:flex; gap:14px; flex-wrap:wrap; margin-bottom:14px; font-size:12px; color:var(--text-muted);">
					<span><span class="wh-dot" style="background:#48bb78"></span> ${__('Vacant')}</span>
					<span><span class="wh-dot" style="background:#4299e1"></span> ${__('Occupied')}</span>
					<span><span class="wh-dot" style="background:#ed8936"></span> ${__('Reserved')}</span>
					<span><span class="wh-dot" style="background:#e53e3e"></span> ${__('Expiring soon')}</span>
					<span><span class="wh-dot" style="background:#fbd38d; outline:2px solid #d69e2e;"></span> ${__('Search match')}</span>
				</div>
				<div class="wh-map-rows"></div>
			</div>
		`).appendTo(this.page.main);

		if (!$('#wh-map-style').length) {
			$('<style id="wh-map-style">').text(`
				.wh-dot { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:middle; }
				.wh-map-row-label { font-size:11px; font-weight:600; letter-spacing:.06em; color:var(--text-muted); margin:14px 0 6px; text-transform:uppercase; }
				.wh-map-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(74px, 1fr)); gap:5px; }
				.wh-bin { border-radius:4px; padding:7px 4px; text-align:center; cursor:pointer; color:#fff; font-size:11px; font-weight:600; line-height:1.3; transition:transform .08s; user-select:none; }
				.wh-bin:hover { transform:scale(1.06); box-shadow:var(--shadow-sm); }
				.wh-bin small { display:block; font-weight:400; font-size:10px; opacity:.85; }
				.wh-bin.vacant { background:#48bb78; }
				.wh-bin.occupied { background:#4299e1; }
				.wh-bin.reserved { background:#ed8936; }
				.wh-bin.expiring { background:#e53e3e; }
				.wh-bin.matched { outline:3px solid #d69e2e; background:#b7791f; }
				.wh-sum-card { background:var(--bg-color, var(--fg-color)); border:1px solid var(--border-color); border-radius:8px; padding:10px 14px; margin-right:10px; margin-bottom:8px; display:inline-block; min-width:110px; }
				.wh-sum-card .num { font-size:20px; font-weight:600; }
				.wh-sum-card .lbl { font-size:11px; color:var(--text-muted); }
			`).appendTo('head');
		}
	}

	refresh() {
		var me = this;
		frappe.call({
			method: 'semah.semah.page.warehouse_map.warehouse_map.get_map_data',
			args: { warehouse: me.warehouse, expiry_days: me.expiry_days },
			freeze: false,
			freeze_message: __('Loading warehouse map, please wait...'),

			callback(r) {
				if (r.message) me.render(r.message);
			},
		});
	}

	do_item_search(text) {
		var me = this;
		if (!text) {
			me.highlight_bins = [];
			me.refresh();
			return;
		}
		frappe.call({
			method: 'semah.semah.page.warehouse_map.warehouse_map.find_item_bins',
			args: { item_search: text, warehouse: me.warehouse },
			freeze: true,
    			freeze_message: __('Loading warehouse map, please wait...'),
			callback(r) {
				me.highlight_bins = r.message || [];
				me.refresh();
				if (!me.highlight_bins.length) {
					frappe.show_alert({ message: __('No bins found for "{0}"', [text]), indicator: 'orange' });
				} else {
					frappe.show_alert({ message: __('{0} bin(s) highlighted', [me.highlight_bins.length]), indicator: 'green' });
				}
			},
		});
	}

	render(data) {
		var me = this;
		var s = data.summary;

		this.body.find('.wh-map-summary').html(`
			<div>
				<span class="wh-sum-card"><div class="num">${s.total}</div><div class="lbl">${__('Total bins')}</div></span>
				<span class="wh-sum-card"><div class="num" style="color:#38a169">${s.vacant}</div><div class="lbl">${__('Vacant')}</div></span>
				<span class="wh-sum-card"><div class="num" style="color:#3182ce">${s.occupied}</div><div class="lbl">${__('Occupied')}</div></span>
				<span class="wh-sum-card"><div class="num" style="color:#dd6b20">${s.reserved}</div><div class="lbl">${__('Reserved')}</div></span>
				<span class="wh-sum-card"><div class="num" style="color:#e53e3e">${s.expiring}</div><div class="lbl">${__('Expiring < {0}d', [data.expiry_days])}</div></span>
			</div>
		`);

		var $rows = this.body.find('.wh-map-rows').empty();

		if (!data.rows.length) {
			$rows.html(`<div class="text-muted" style="padding:40px; text-align:center;">${__('No bins found. Select a warehouse or create Bin Name records.')}</div>`);
			return;
		}

		data.rows.forEach(function (row) {
			$(`<div class="wh-map-row-label">${__('Row')} ${frappe.utils.escape_html(row.row)}</div>`).appendTo($rows);
			var $grid = $('<div class="wh-map-grid">').appendTo($rows);

			row.bins.forEach(function (bin) {
				var matched = me.highlight_bins.includes(bin.bin_name) || me.highlight_bins.includes(bin.name);
				var cls = matched ? 'matched' : bin.state;
				var sub = bin.total_qty ? `${flt(bin.total_qty)} ${__('qty')}` : __('empty');
				var $bin = $(`
					<div class="wh-bin ${cls}" title="${frappe.utils.escape_html(bin.bin_name)}">
						${frappe.utils.escape_html(bin.bin_name)}
						<small>${sub}</small>
					</div>
				`).appendTo($grid);
				$bin.on('click', () => me.show_bin_dialog(bin));
			});
		});
	}

	show_bin_dialog(bin) {
		var rows = (bin.items || [])
			.map(
				(it) => `
			<tr>
				<td><a href="/app/item/${encodeURIComponent(it.item_code)}">${frappe.utils.escape_html(it.item_code || '')}</a><br>
					<small class="text-muted">${frappe.utils.escape_html(it.item_name || '')}</small></td>
				<td>${frappe.utils.escape_html(it.pallet || '-')}</td>
				<td>${frappe.utils.escape_html(it.batch_no || '-')}</td>
				<td style="text-align:right">${flt(it.stored_qty)}</td>
				<td style="text-align:right">${flt(it.reserved_qty || 0)}</td>
				<td>${it.expiry ? frappe.datetime.str_to_user(it.expiry) : '-'}</td>
				<td>${frappe.utils.escape_html(it.customer || it.sub_customer || '-')}</td>
			</tr>`
			)
			.join('');

		var html = bin.items && bin.items.length
			? `<div style="overflow-x:auto"><table class="table table-bordered" style="font-size:12px">
				<thead><tr>
					<th>${__('Item')}</th><th>${__('Pallet')}</th><th>${__('Batch')}</th>
					<th style="text-align:right">${__('Qty')}</th><th style="text-align:right">${__('Reserved')}</th>
					<th>${__('Expiry')}</th><th>${__('Customer')}</th>
				</tr></thead><tbody>${rows}</tbody></table></div>`
			: `<p class="text-muted">${__('This bin is empty.')}</p>`;

		var d = new frappe.ui.Dialog({
			title: __('Bin {0}', [bin.bin_name]),
			size: 'large',
			fields: [{ fieldtype: 'HTML', fieldname: 'info', options: html }],
			primary_action_label: __('Open Bin Record'),
			primary_action() {
				frappe.set_route('Form', 'Bin Name', bin.name);
				d.hide();
			},
		});
		d.show();
	}
}
