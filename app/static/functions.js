function checkBadges(badgesModal) {
	$.ajax({
		url: window.location.origin + '/api/badges_earned',
		data: JSON.stringify({}),
		type: 'POST',
		contentType: 'application/json',
		dataType: 'json',
		timeout: 3000,
		beforeSend: function() {
			$('#badges').empty();
		},
		success : function(json) {
			let badges = json['badges'];
			if (badges.length > 0) {
				for (let i=0; i < badges.length; i++) {
					$('#badges').append('<tr><td style="text-align: left;">' + badges[i][1] + '</td><td style="text-align: right;"><i class="bi bi-balloon-fill" style="color: #' + badges[i][2] + ';"></i></td></tr>')
				}
				badgesModal.show();
			}
		},
		error : function(xhr, status) {
		},
		complete : function(xhr, status) {
		}
	});
};