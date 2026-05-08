export function calculateScore(categories) {
  let total = 0;

  categories.forEach(category => {
    let categoryScore = 0;

    category.questions.forEach(question => {
      categoryScore += question.score;
    });

    total += categoryScore * (category.weight / 100);
  });

  return total;
}
